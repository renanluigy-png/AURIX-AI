# Third-party components

This project uses third-party software and models in addition to the AURIX source code.

## Kokoro v1.0 neural TTS model

- Model: Kokoro-82M v1.0, ONNX FP16 export.
- ONNX source/export: https://github.com/thewh1teagle/kokoro-onnx
- Release assets: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1
- Base model: https://huggingface.co/hexgrad/Kokoro-82M
- Model weights and voice styles: Apache License 2.0.
- The model and voice pack are downloaded on first use, not bundled in the installer. Both files are pinned by SHA-256 and verified before loading.

## TugaPhone Portuguese phonemizer

- Package: `tugaphone==0.2.1`.
- Project: https://github.com/TigreGotico/tugaphone
- License: Apache License 2.0.
- Used with the `pt-BR` dialect and the lightweight rule-based/dummy POS mode to avoid loading large NLP models.

## Kokoro ONNX reference implementation

- Project: https://github.com/thewh1teagle/kokoro-onnx
- License: MIT.
- AURIX uses ONNX Runtime directly and does not import the reference Python wrapper or its eSpeak-based phonemizer.

## Existing local voice fallback

- Component: `pyttsx3`.
- Project: https://github.com/nateshmbhat/pyttsx3
- License: MPL-2.0.
