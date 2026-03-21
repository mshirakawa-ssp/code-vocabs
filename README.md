# code-vocabs

这个工具可以帮助程序员学习IT单词。
我们从VS Code的翻译文件中提取单词。

## 功能 (Features)

* **双向学习**: 可以选择“学习日语”或“学习中文”。
* **自动播放**: 自动读单词，卡片会自动翻转。适合开车或休息时使用。
* **分类学习**: 可以选择不同的分类（如 Debug, Terminal）。
* **标记功能 (Mark)**: 记不住的单词可以打星号，以后专门复習。

## 计划 (Roadmap)

* [ ] 支持 Chrome 浏览器翻译文件
* [ ] 支持 Docker 部署
* [ ] 优化 UI/UX

## 贡献 (Contributing)

我们非常欢迎大家的帮助！如果你有想法，可以这样做：

1.  **提建议**: 如果想要新的功能，请在 **Issues** 留言。
2.  **改进代码**: 如果你写了更好的代码，请提交 **Pull Request (PR)**。

## 开始使用 (Quick Start)

1.  **准备**:
    ```bash
    pip install pypinyin pykakasi
    ```

2.  **生成数据**:
    把 `ja.json` 和 `ch.json` 放在 `data/raw/` 文件夹。
    运行：
    ```bash
    python scripts/generate_dict.py
    ```

3.  **打开网页**:
    直接用 **浏览器** 打开 `index.html`，或者使用 VS Code 的 `Live Server`。

## 文件夹结构 (Project Structure)

* `index.html`: 网页主文件
* `app.js`: 网页逻辑
* `data/`: 存放单词数据 (JSON)
* `scripts/`: 制作数据的 Python 脚本
* `.gitignore`: 排除不需要上传的文件（如 .venv）

## 开源协议 (License)

本项目基于 **MIT License** 开源。
(数据来源于 VS Code 等开源项目，版权归原作者所有。)