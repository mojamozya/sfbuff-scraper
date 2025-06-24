# 準備
## まえがき
正直あんまりPython詳しくないけど、「なんか触ってみたいな」ぐらいの気持ちで準備したので、インストール方法とか適当です。

## Pythonのインストール
[公式ページ](https://www.python.org/downloads/)から頑張ってインストールしてください。
お節介な注意点ですが、`Add python.exe to PATH`にチェックを入れるなり、自分でPATH通すなりしてください。

## Python 標準の仮想環境 venv を生成
```sh
python -m venv .venv
```

## 仮想環境をアクティブ化
要は`.venv`ディレクトリの中にある`activate`的な実行ファイルを実行すればいいらしいです。
それぞれのOSに合わせた方法で適当にやってください。

### shellの場合
```sh
source .venv/bin/activate
```

### PowerShellの場合
```ps
.venv\Scripts\Activate.ps1
```

### コマンドプロンプトの場合
```cmd
.venv\Scripts\activate.bat
```

## 依存パッケージをインストール
```sh
pip install --upgrade pip
pip install requests beautifulsoup4
```

# 使い方
適当なブラウザで[sfbuffさん](https://www.sfbuff.site/)でプレイヤーを指定し、`Ranked History`の画面を開き、`My Character`と`From`と`To`を指定してください。

そうすると、URLがクエリを含むものになりますので、それをそのままコピペして下記のような感じで雰囲気でコマンドを叩いてください。

```sh
python sfbuff_rank_history.py "https://www.sfbuff.site/fighters/XXXXXXXXX/ranked?home_character=1&played_from=2025-04-01&played_to=2025-04-30" > dist/result.json
```

要はコマンド叩いたあとに`dist/適当なファイル名.json`に吐き出しているだけなので、好みで適当に名前をつけてください。`ryu2025-04-01-2025-04-30.json`とかでもなんでも。

URLじゃなくてオプションで指定する方法も実装していますが、説明が面倒なので、

* コードを読んで意味が分かるひと
* いちいちブラウザ開くのが面倒な人

は使ってみてください。