import sqlite3
import pandas as pd

conn = sqlite3.connect('ecogrid.db')

# 檢查原始數據
print("=== 資料庫原始數據（前 5 筆）===")
df = pd.read_sql_query("SELECT load_kw, solar_kw, wind_kw FROM power_logs LIMIT 5", conn)
print(df)
print(f"\n統計:")
print(f"Load 平均: {df['load_kw'].mean():.2f} kW")
print(f"Load 範圍: {df['load_kw'].min():.2f} ~ {df['load_kw'].max():.2f} kW")

# 檢查 ETL 處理後的數據
print("\n=== 檢查 ETL 轉換 ===")
from src.ecogrid.data.etl_pipeline import ETLPipeline

etl = ETLPipeline()
data, path = etl.run_pipeline(days=7)

print(f"ETL 輸出欄位: {data.columns.tolist()}")
print(f"\nETL 數據樣本（前 3 筆）:")
print(data[['load_mw', 'solar_mw', 'wind_mw']].head(3))
print(f"\n統計:")
print(f"load_mw 平均: {data['load_mw'].mean():.6f} MW = {data['load_mw'].mean() * 1000:.2f} kW")
print(f"load_mw 範圍: {data['load_mw'].min():.6f} ~ {data['load_mw'].max():.6f} MW")

conn.close()
