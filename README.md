# D+2 / D+3 实时电价预测

本目录包含 TimesFM 2.5 模型权重、推理代码和预测程序。复制整个文件夹后无需原项目目录；运行时需可访问的源数据库，选择本地写入时还需本地 MySQL。

建议使用 Python 3.10 或 3.11，创建虚拟环境后执行 `pip install -r requirements.txt`。默认将结果写入源数据库已有的 `epf_rt_d2_d3_forecast_result` 表，源数据库账号需要该表的 INSERT 和 UPDATE 权限；如将 `result_target` 设为 `local`，需先在本地 MySQL 创建数据库并执行 `schema_mysql.sql`。

## 数据库配置和运行

数据库地址、用户名和密码保存在项目内的 `config.local.json`，包含 `source`（服务器）和 `local`（可选本地结果库）两组，`result_target` 设为 `source` 时写入远程结果表，设为 `local` 时写入本地结果表。首次迁移可参考 `config.example.json` 创建自己的 `config.local.json` 并填写真实连接信息。该文件包含明文密码，已列入 `.gitignore`；分享或打包项目前请排除该文件，并在新环境单独配置。

在项目目录中运行：

```powershell
python main.py
```

默认使用当天作为预测日；可通过 `python main.py --date 2026-11-27` 指定日期。运行环境的本地时区应设为中国时间。环境变量 `SOURCE_DB_HOST`、`SOURCE_DB_PORT`、`SOURCE_DB_USER`、`SOURCE_DB_PASSWORD`、`SOURCE_DB_NAME` 和对应的 `LOCAL_DB_*` 如有设置，将覆盖配置文件对应字段。

历史实时电价仅使用截至 D−1 日 24:00（D 日 00:00，含）的 60 天数据，按三个 8 小时组分别预测。天气数据的发布时间、入库时间及更新时间均不得晚于程序实际启动时间；该时间记入结果 remark。按历史日期重跑时，天气截止时间也是实际启动时间，不能视为严格的历史时点回测。

相同预测日期、模型和预测时间重复运行时更新对应记录。时标为市场小时结束时刻：目标日第 24 点写作次日 00:00，提前期及小时写入 remark。历史实时电价和 A1 发布版本无法完全回溯，回放结果属于探索性结果。
