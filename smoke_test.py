"""Isolated synthetic DB integration smoke test; runs the bundled model."""
import os,sys,types
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
os.environ.update(SOURCE_DB_HOST='fixture',SOURCE_DB_USER='fixture',SOURCE_DB_PASSWORD='fixture',SOURCE_DB_NAME='fixture',LOCAL_DB_PASSWORD='fixture')
day=pd.Timestamp('2025-01-03');origin=day+pd.Timedelta(hours=14)
hi=pd.date_range(end=origin,periods=1440,freq='h')
times=pd.date_range(hi[0]-pd.Timedelta(hours=1),day+pd.Timedelta(days=4),freq='h')
written=[]

class Cursor:
    def execute(self,sql,params=None):
        if 'FROM epf_market_data' in sql:
            self.description=[('data_time',),('price_realtime',)];self.rows=[(t.to_pydatetime(),float(300+30*np.sin(i/24))) for i,t in enumerate(hi)]
        elif 'FROM a1_weekly_forecast' in sql:
            self.description=[(x,) for x in ('market_date','period_no','forecast_grid_load','forecast_dispatch_load','forecast_renewable_generation')]
            self.rows=[(d.date(),i,60000+i*5,50000+i*3,10000+i*2) for d in pd.date_range(hi[0].normalize()-pd.Timedelta(days=1),day+pd.Timedelta(days=3)) for i in range(1,97)]
        elif 'FROM hourly_weather_forecast' in sql:
            names=('city_en','datetime','forecast_issued_at','created_at','updated_at','model_name','temperature_2m','precipitation','wind_speed_10m','shortwave_radiation')
            self.description=[(x,) for x in names];t=(origin-pd.Timedelta(days=4)).to_pydatetime()
            self.rows=[('Jinan',x.to_pydatetime(),t,t,t,'fixture',10+np.sin(i/24),0.,3.,100.) for i,x in enumerate(times)]
        elif 'SELECT COUNT(*)' in sql:self.rows=[(len(written),)]
        else:raise AssertionError(sql)
    def fetchall(self):return self.rows
    def fetchone(self):return self.rows[0]
    def executemany(self,sql,rows):written.extend(rows)
    def close(self):pass
class Conn:
    def cursor(self):return Cursor()
    def close(self):pass
    def commit(self):pass
    def rollback(self):raise AssertionError('rollback')

import mysql.connector
mysql.connector.connect=lambda **kwargs:Conn()
import main
sys.argv=['main.py','--date','2025-01-03']
main.main()
assert len(written)==48 and len({r[1] for r in written})==48
assert sum('D+2' in r[4] and 'weather=1' in r[4] for r in written)==24
assert sum('D+3' in r[4] and 'price_only=1' in r[4] for r in written)==24
assert all(np.isfinite(r[2]) for r in written)
print('PASS 48 hours, weather D+2 and Friday price-only D+3, bundled model')
