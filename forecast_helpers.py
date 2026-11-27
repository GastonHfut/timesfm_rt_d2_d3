import numpy as np

FEATURES = ["forecast_grid_load", "forecast_dispatch_load", "forecast_renewable_generation"]

def selected(index, first):
    hour = (index.hour - 1) % 24 + 1
    return (hour >= first) & (hour < first + 8)

def make_covariates(xh,xf,first,n_target,hist_times,future_times):
    """Drop incomplete target features; fill other gaps by same-hour past median."""
    cov={}; audit={}
    hh=(hist_times.hour-1)%24+1;fh=(future_times.hour-1)%24+1
    assert len(hh)==len(xh) and len(fh)==len(xf)
    for i,name in enumerate(FEATURES):
        historical=np.asarray(xh[:,i],float);future=np.asarray(xf[:,i],float)
        valid=np.isfinite(historical); fvalid=np.isfinite(future)
        audit[name]={'hist_observed':int(valid.sum()),'hist_total':len(historical),
                     'future_observed':int(fvalid.sum()),'future_total':len(future),'target_observed':int(fvalid[-n_target:].sum())}
        if not fvalid[-n_target:].all():
            audit[name]['status']='omitted_target_missing';continue
        full=np.concatenate([historical,future]);hours=np.concatenate([hh,fh]);missing=~np.isfinite(full);filled=full.copy()
        for hour in np.unique(hours[missing]):
            history_at_hour=historical[(hh==hour)&valid]
            if not len(history_at_hour):break
            filled[missing&(hours==hour)]=np.median(history_at_hour)
        if not np.isfinite(filled).all() or not valid.any():
            audit[name]['status']='omitted_no_same_hour_history';continue
        cov[name]=[filled.astype(np.float32)];audit[name]['status']='used'
        if missing.any():cov[name+'_missing']=[missing.astype(np.float32)]
    return cov,audit

CITIES=('Jinan','Qingdao','Zibo','Zaozhuang','Dongying','Yantai','Weifang','Jining','Taian','Weihai','Rizhao','Linyi','Dezhou','Liaocheng','Binzhou','Heze')
FIELDS=('temperature_2m','precipitation','wind_speed_10m','shortwave_radiation')
READ_COLS=('city_en','datetime','forecast_issued_at','created_at','updated_at','model_name',*FIELDS)

