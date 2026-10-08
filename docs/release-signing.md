# Signing a Kara release

Kara 0.3.4 signs `Kara.exe`, both installers and their uninstallers when the release
environment supplies `KARA_SIGN_COMMAND`. The command must contain `{file}`;
Kara substitutes the path of the file being signed.

Use a code-signing certificate or managed signing provider that keeps its private
key outside the repository. The command must sign with SHA-256 and request an
RFC 3161 SHA-256 timestamp. For example, the shape of a SignTool command is:

```text
signtool sign /fd SHA256 /tr https://timestamp.example.invalid /td SHA256 /a {file}
```

The timestamp service and certificate selector belong to the chosen provider.
Do not commit a `.pfx` file, its password, or provider credentials.

For a local build, set `KARA_SIGN_COMMAND` in the build environment before
running `packaging/build.py`. Verify the Authenticode signatures of the built
application and both installers before approving publication. Without the
command, the build is unsigned; do not claim it is signed in the release notes.
