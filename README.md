# Construct 3 Copilot

[中文](README_CN.md) | **English**

A local task runtime for Construct 3. Execute installed Agent-Skills, persist results, and serve the QQ bot adapter.

Construct tools, prompts, generation and project edits live in `copilot/providers/construct3/`.
The QQ bot loads that implementation from its configured Copilot checkout. See the [layout guide](docs/layout.md).

## Local runtime and QQ adapter

Use Python 3.10+ and a sibling `Construct3-Agent-Skills` checkout.
Each provider script keeps its own dependencies.

```powershell
python -m copilot capabilities
python -m copilot run lookup_ace --locale zh-CN --limit 3000 -- System wait
```

The QQ host keeps model configuration, message delivery and application loading.
Its Construct adapter connects to the application in this repository.
Copilot executes its Construct tools and records their results.
See the [framework guide](docs/framework.md) for the channel and application boundaries.
The [runtime guide](docs/runtime.md) covers configuration and verification limits.

## Project tools

For folder projects and `.c3p` files, use
[Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills).
It owns the project tools and prompts, and
[Construct3-RAG](https://github.com/XHXIAIEIN/Construct3-RAG) owns their source data.

## License

[MIT](LICENSE)
