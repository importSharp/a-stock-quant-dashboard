# a-stock-data Web

网页只读取 `public/data/a-stock-data.json`，由根目录
`scripts/a_stock_data_snapshot.py` 使用 a-stock-data 端点生成。

从项目根目录运行：

```powershell
.\scripts\mobile-refresh.ps1 -Once
.\scripts\web.ps1
```

访问 `http://localhost:3000/`。任意代码分析由 `/api/stock` 按需读取腾讯实时行情和腾讯K线。
