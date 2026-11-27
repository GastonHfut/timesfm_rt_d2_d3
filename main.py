"""Hourly D+2/D+3 TimesFM experiment; reads remote DB, writes local MySQL."""
import argparse, json, os, pathlib, sys
import numpy as np
import pandas as pd
import mysql.connector

PROJECT_DIR=pathlib.Path(__file__).resolve().parent
import forecast_helpers as helpers

def load_db_config(path):
    config = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    target = config.get('result_target', 'source')
    if target not in ('source', 'local'):
        raise ValueError('result_target 必须为 source 或 local')
    result = {}
    for section, prefix, defaults in (
        ('source', 'SOURCE_DB_', {}),
        ('local', 'LOCAL_DB_', {'host':'127.0.0.1', 'port':3306, 'user':'root', 'database':'timesfm_rt_forecast'}),
    ):
        values = dict(defaults)
        values.update(config.get(section, {}))
        for field, suffix in (('host','HOST'),('port','PORT'),('user','USER'),('password','PASSWORD'),('database','NAME')):
            if prefix+suffix in os.environ:
                values[field] = os.environ[prefix+suffix]
        missing = [field for field in ('host','user','password','database') if not values.get(field)]
        if missing and (section == 'source' or target == 'local'):
            raise ValueError(f'{section} 数据库配置缺失: {", ".join(missing)}；请填写 {path}')
        result[section] = {**values, 'port': int(values.get('port', 3306)), 'connection_timeout': 10}
    result['result_target'] = target
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--date',default=None);args=parser.parse_args()
    day=pd.Timestamp(args.date or pd.Timestamp.now().date()).normalize();origin=day+pd.Timedelta(hours=14)
    if pd.Timestamp.now()<origin: raise ValueError('Prediction time must be after D 14:00')
    cfg=load_db_config(PROJECT_DIR/'config.local.json')
    conn=mysql.connector.connect(**cfg['source'])

    def query(sql,params):
        cur=conn.cursor();cur.execute(sql,params); rows=cur.fetchall();columns=[c[0] for c in cur.description];cur.close();return pd.DataFrame(rows,columns=columns)
    hi=pd.date_range(end=day,periods=1440,freq='h')
    prices=query('SELECT data_time,price_realtime FROM epf_market_data WHERE data_time BETWEEN %s AND %s',(hi[0].to_pydatetime(),hi[-1].to_pydatetime()))
    prices['data_time']=pd.to_datetime(prices.data_time);prices=prices.set_index('data_time').sort_index();assert not prices.index.duplicated().any()
    y=prices.reindex(hi).price_realtime.to_numpy(dtype=float)
    if not np.isfinite(y).all():raise ValueError('Missing hourly realtime prices in 60-day history')
    a=query('SELECT market_date,period_no,forecast_grid_load,forecast_dispatch_load,forecast_renewable_generation FROM a1_weekly_forecast WHERE market_date BETWEEN %s AND %s',((hi[0]-pd.Timedelta(days=1)).date(),(day+pd.Timedelta(days=3)).date()))
    a.market_date=pd.to_datetime(a.market_date);assert not a.duplicated(['market_date','period_no']).any();a['hour']=(a.period_no-1)//4+1
    for f in helpers.FEATURES:a[f]=pd.to_numeric(a[f],errors='coerce')
    g=a.groupby(['market_date','hour'])[helpers.FEATURES];features=g.mean().where(g.count()==4);features.index=pd.DatetimeIndex([d+pd.Timedelta(hours=int(h)) for d,h in features.index]);features=features.sort_index()
    columns=','.join('`'+x+'`' for x in helpers.READ_COLS)
    w=query('SELECT '+columns+' FROM hourly_weather_forecast WHERE datetime BETWEEN %s AND %s AND forecast_issued_at<=%s AND created_at<=%s AND updated_at<=%s',((hi[0]-pd.Timedelta(hours=1)).to_pydatetime(),(day+pd.Timedelta(days=4)).to_pydatetime(),origin.to_pydatetime(),origin.to_pydatetime(),origin.to_pydatetime()));conn.close()
    for col in ['datetime','forecast_issued_at','created_at','updated_at']:w[col]=pd.to_datetime(w[col])
    w=w[w.city_en.isin(helpers.CITIES)].copy()
    for col in helpers.FIELDS:w[col]=pd.to_numeric(w[col],errors='coerce')
    w=w.dropna(subset=list(helpers.FIELDS));w['available_at']=w[['forecast_issued_at','created_at','updated_at']].max(axis=1)
    w=w.sort_values(['city_en','datetime','forecast_issued_at','available_at'])
    historical=w.drop_duplicates(['city_en','datetime'],keep='last')
    hist=historical.groupby('datetime')[list(helpers.FIELDS)].mean();earliest=historical.datetime.min()
    future_records=w[w.available_at<=w.datetime.clip(upper=origin)].drop_duplicates(['city_en','datetime'],keep='last')
    future=future_records.groupby('datetime')[list(helpers.FIELDS)].mean()
    sys.path.insert(0,str(PROJECT_DIR/'vendor'));os.environ.setdefault('JAX_PLATFORMS','cpu')
    import timesfm
    mod=sys.modules['timesfm.timesfm_2p5.timesfm_2p5_torch'];old=mod.hf_hub_download;mod.hf_hub_download=lambda *a,**kw:None if kw.get('force_download') else old(*a,**kw)
    try:model=timesfm.TimesFM_2p5_200M_torch.from_pretrained(str(PROJECT_DIR/'models/timesFM'),torch_compile=False)
    finally:mod.hf_hub_download=old
    model.compile(timesfm.ForecastConfig(max_context=480,max_horizon=128,normalize_inputs=True,use_continuous_quantile_head=True,force_flip_invariance=True,infer_is_positive=False,fix_quantile_crossing=True,return_backcast=True))
    out=[]
    for lead in (2,3):
        target=day+pd.Timedelta(days=lead);fi=pd.date_range(start=day+pd.Timedelta(hours=1),end=target+pd.Timedelta(days=1),freq='h');weekend=origin.weekday() in (5,6) or (origin.weekday()==4 and lead==3)
        for first in (1,9,17):
            hm=helpers.selected(hi,first);fm=helpers.selected(fi,first);hs=hi[hm];fs=fi[fm];ys=y[hm];xh=features.reindex(hs).to_numpy(float);xf=features.reindex(fs).to_numpy(float)
            cov,_=helpers.make_covariates(xh,xf,first,8,hs,fs)
            if weekend:cov={}
            use_weather=False
            if cov and pd.notna(earliest) and hs.min()>=earliest:
                past=hist.reindex(hs).to_numpy(float);fut=future.reindex(fs).to_numpy(float);missing=~np.isfinite(past).all(axis=1)
                for hour in np.unique(hs.hour[missing]):
                    mask=(hs.hour==hour)&missing;ok=(hs.hour==hour)&~missing
                    if ok.any():past[mask]=np.median(past[ok],axis=0)
                if np.isfinite(past).all() and np.isfinite(fut).all():
                    if missing.any():cov['weather_missing']=[np.concatenate([missing,np.zeros(len(fs),dtype=bool)]).astype(np.float32)]
                    for i,name in enumerate(helpers.FIELDS):cov['weather_'+name]=[np.concatenate([past[:,i],fut[:,i]]).astype(np.float32)]
                    use_weather=True
            if cov:pred,_=model.forecast_with_covariates(inputs=[ys.astype(np.float32)],dynamic_numerical_covariates=cov,xreg_mode='xreg + timesfm',normalize_xreg_target_per_input=True,ridge=1e-2,force_on_cpu=True)
            else:pred,_=model.forecast(horizon=len(fs),inputs=[ys.astype(np.float32)])
            values=np.asarray(pred[0])[-8:];assert len(values)==8 and np.isfinite(values).all()
            for n,v in enumerate(values):out.append((day.date(),(target+pd.Timedelta(hours=first+n)).to_pydatetime(),float(v),'timesfm25_60d_8h',f'D+{lead}; hour={first+n}; weather={int(use_weather)}; price_only={int(not cov)}'))
    assert len(out)==48 and len({v[1] for v in out})==48
    local=mysql.connector.connect(**cfg[cfg['result_target']])
    try:
        cur=local.cursor();cur.executemany('INSERT INTO epf_rt_d2_d3_forecast_result (forecast_date,forecast_time,forecast_value,model_name,remark) VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE forecast_value=VALUES(forecast_value),remark=VALUES(remark)',out);local.commit();cur.execute('SELECT COUNT(*) FROM epf_rt_d2_d3_forecast_result WHERE forecast_date=%s AND model_name=%s',(day.date(),'timesfm25_60d_8h'));print('ROWS',cur.fetchone()[0]);cur.close()
    except Exception:local.rollback();raise
    finally:local.close()
    print('prediction completed for',day.date(),'weather hours',sum('weather=1' in x[4] for x in out))

if __name__=='__main__':main()
