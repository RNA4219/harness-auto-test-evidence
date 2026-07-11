---
intent_id: INT-HATE-PLATFORM-PLUGIN-SANDBOX-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-11
next_review_due: 2026-07-25
---

# Platform Plugin Sandbox Specification

本書は detector plugin の実行境界、resource limit、trust enforcement、
failure isolation を定義する。v0.2.0 の local runner は fail-closed な
process runner であり、filesystem/network を完全隔離する sandbox ではない。

## 1. Execution Modes

| Mode | Purpose | Default / strict profile |
|---|---|---|
| `in_process_builtin` | built-in trusted detectors | local runner の対象外 |
| `subprocess_local` | workspace plugin | default は `--allow-local-exec` 必須、release/regulated は常時拒否 |
| `containerized` | hosted/enterprise plugin | runner evidence が別途必要 |
| `disabled` | denied plugin | 常時未実行 |

実行順序は manifest/schema validation、mode/trust/revocation/compatibility/resource
preflight、明示許可確認、process 起動、出力検証で固定する。preflight が hold/block
を返した場合や `disabled` の場合は process を起動しない。

## 2. Authorization and Trust Boundary

`subprocess_local` は default profile でも `--allow-local-exec` がない限り起動しない。
release/regulated profile はフラグの有無にかかわらず local subprocess を拒否する。

`signature_valid`、`signed`、`trusted` は外部検証証跡の入力値であり、HATE自身が
暗号学的署名を検証した結果ではない。v0.2.0 の安全境界はpreflightと明示実行許可である。

## 3. Local Runner Controls

強制するcontrol:

- timeout と process tree termination
- stdout/stderr の一時ファイル収集と合計byte上限
- 最小環境変数と明示env allowlist
- pluginごとの一時working directory
- crash、timeout、出力超過、invalid JSON のreport化

Windowsは `taskkill /T /F`、POSIXは新規process groupと `killpg` を使う。
reportには `execution_attempted`、`execution_authorized`、
`authorization_source`、`denial_reasons`、`enforced_controls`、
`unenforced_controls` を記録する。

強制しないcontrol:

- filesystem isolation
- network isolation
- portableなmemory limit

したがってlocal runnerを「完全sandbox済み」と表現してはならない。release/regulated
用途ではcontainerized runnerの独立したevidenceを要求する。

## 4. Output Contract

Plugin outputはJSONでなければならない。malformed outputは
`plugin_output_invalid` finding、timeoutは `plugin_timeout`、出力超過は
`plugin_output_budget_exceeded`、非zero終了は `plugin_execution_failed`
としてreportへ変換し、platform processをcrashさせない。

## 5. Required Test Coverage

- denied/unsigned/untrusted/revoked/disabled pluginがsentinelを起動しない
- default profileでは明示許可とpreflight passの両方が必要
- release/regulatedでは明示許可があっても未実行
- timeout、親子process、出力超過、crash、invalid JSONをreport化
- enforced/unenforced controlと署名検証境界をreportへ保持
