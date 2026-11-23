# 碎玻璃配载单

## 启动

```sh
docker compose up --build
```

打开 `http://localhost:18442`，切换干净样例与脏样例，查看数据判定和来源行。
可以在工作台上传同格式的 UTF-8 JSON。签核后可重跑并下载带输入快照、运行清单与证据的 JSON 凭证。

## 核验

```sh
docker compose exec -T app pytest -q
```

本机也可安装 `requirements.txt` 后执行 `python -m pytest -q`。
SQLite 默认保存在 `instance/ledger.sqlite3`，容器使用 `state` 命名卷。需要重建时，先备份归档，再执行 `docker compose down -v`。

## 模块

磅单采集、含水抽样、色级判定、干重折算、目标配载、装车对账、签单凭证、批次结算。
批次结算按已齐证据裁决：三证齐全方可确认放款；磅单冲突整批暂扣；含水或分级缺证只给暂估并暂扣，不进应付。同批重试不新增结算单，新证据升版并保留旧版，正式确认失败时旧版原样保留。
接口索引在 `/docs`，字段和边界见 [数据字典](docs/DATA-DICTIONARY.md)，规则与测试见 [深度登记](docs/DEPTH.md)。

已下载的凭证可用 `python -m app.modules.m7_archive.verify 证据.json` 检查输入、结果和签核摘要。
