# Windows preview for OpenCode Console sign-in

This preview uses DeepSeek Harness `0.2.2-rc.1`, Chimney `0.20.2`, and the official `@opencode/console` `0.1.16` CLI. It keeps the Console sign-in, DSH settings, and sessions together under `%LOCALAPPDATA%\devneya-opencode-browser-preview`. Use the Node.js `24.22.0` distribution with npm.

```powershell
pwsh -File preview/opencode-browser/run.ps1 -Action Install
pwsh -File preview/opencode-browser/run.ps1 -Action Connect
pwsh -File preview/opencode-browser/run.ps1 -Action Start
```

Use `-NodePath` if the bundled `node.exe` is outside `PATH`. Start uses the current directory as the workspace. Use `-Action Status` to check which Console workspace is connected.

During Connect, check the displayed code in the OpenCode browser window and confirm the workspace. The official plugin handles token refresh and applies the selected workspace's provider and tool policies. When the workspace supplies a model catalog, its models appear in the preview's selector. Go models require a Go entitlement in the selected workspace. [OpenCode Console integration](https://opencode.ai/console/integrations/deepseek-harness)

The preview pins the DSH dependencies of the activity panel because its published peer ranges predate the DSH version supported by Chimney. DSH's standalone `dsh-invariants` package is pinned at `0.2.0-rc.2` for the panel.
