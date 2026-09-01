# Decrypted AGE2 UI-string patcher

`patch_uistring.py` replaces only an exact `id + Japanese source` match in an
already decrypted UI-string DAT/EPK payload. It deliberately does not
implement FSNr EPK decryption/encryption and cannot turn the resulting DAT into
a game-ready `uistring.epk` by itself.

```powershell
python age2/tools/uistring/patch_uistring.py `
  "X:\Work\uistring.dec" `
  --changes "X:\Work\ui.ja-target.tsv" `
  --target-column target_text `
  --output "X:\Work\uistring.localized.dec"
```

The TSV requires `id`, `jp`, and the column named by `--target-column`; the
default target column is the existing Chinese `zh_cn`. The output must be a new path
and must not alias the decrypted input or change table. Completed UTF-8 bytes
are fsynced under a same-directory temporary name and atomically published; an
existing reviewed output is never overwritten.

This project currently relies on separately held FSNr tooling for the outer
EPK layer. Record that input/tool version and compare the final encrypted file
in game; a successful plaintext replacement is not proof of a valid EPK.
