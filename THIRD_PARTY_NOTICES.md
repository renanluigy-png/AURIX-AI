# Third-party components

This project uses third-party software and models in addition to the AURIX source code.

## Piper Plus

- Package: `piper-plus[cpu]`, pinned to version 2.0.2.
- License: MIT.
- Project: https://github.com/ayutaz/piper-plus
- PyPI: https://pypi.org/project/piper-plus/

## Brazilian Portuguese Faber Medium voice

- Model: `pt_BR-faber-medium`.
- Source: https://huggingface.co/rhasspy/piper-voices/tree/4ddc3e5fe132918785d98c0c8c7d6ca295c0034c/pt/pt_BR/faber/medium
- Language: Brazilian Portuguese (`pt_BR`).
- Model repository license metadata: MIT. The associated Faber training dataset is marked CC0 in its model card.
- Downloaded on first use, not bundled in the installer. The ONNX file is SHA-256 verified before loading.

## Existing local voice fallback

- Component: `pyttsx3`.
- Project: https://github.com/nateshmbhat/pyttsx3
- License: MPL-2.0.
