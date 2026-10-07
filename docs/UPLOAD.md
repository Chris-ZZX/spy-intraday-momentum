# 上传到GitHub

建议仓库名：`spy-intraday-momentum`。

可用仓库描述：`SPY intraday momentum replication with volatility targeting, LSTM risk allocation, and TCN/Ridge entry-filter experiments.`

可选Topics：`algorithmic-trading`、`intraday-momentum`、`backtesting`、`spy`、`pytorch`、`lstm`、`tcn`。

## 网页上传

1. 解压项目包。确认文件夹中有`README.md`、`Strategy.ipynb`、`.gitignore`以及`docs/`、`results/`、`assets/`、`scripts/`、`config/`。
2. 在GitHub创建仓库，将上述文件及目录上传到**仓库根目录**，提交后检查主页是否展示README、图片能否加载、Notebook能否打开。不要把ZIP作为项目的唯一文件上传。
3. `.gitignore`是隐藏文件，确认也已上传。之后生成的行情CSV、缓存、环境目录和凭据文件应留在本地。

不要把外层项目文件夹再次嵌套进仓库，否则README不会位于根目录。若新仓库已自动生成README，将它替换成本项目README。

## 使用Git上传

先在GitHub创建一个空仓库，然后在解压后的项目根目录执行。把`YOUR_USERNAME`替换成自己的GitHub用户名，远程仓库名替换成实际名称：

```bash
git init
git add .
git status
git commit -m "Add SPY momentum replication and research results"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/spy-intraday-momentum.git
git push -u origin main
```

提交前查看`git status`：应包含Notebook、说明、结果表和图片，不应包含`.env`、原始行情CSV、`alpaca_cache/`或`.venv/`。第一次上传后，后续修改在同一仓库正常提交即可。

仓库没有预先添加开源许可证；选择并添加许可证前，请确认你希望采用的授权方式以及可公开材料的范围。
