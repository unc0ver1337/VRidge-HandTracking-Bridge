# Core ML backend 2.5

Проверенный preview перенесён в основной клиент 2.5. Windows и GlassVR используют прежний совместимый протокол.
640×480/30 FPS, две руки и Back+Start сохранены; wire protocol MPBR/v2 совместим.

Основа: [Vimal Mollyn / fasthands](https://github.com/VimalMollyn/Mediapipe-Hands-PyTorch-CoreML),
revision 565d18818104a315887c611c84125f382dfcf6aa. Используются stock Google
MediaPipe fp16 модели из его Core ML-порта; SHA256 исходного hand_landmarker.task
совпадает с 2.0. WHIM fine-tuned checkpoints не используются. Модели не стали
«умнее»: проверяется другой runtime и возможность снизить задержку/нагрев.

Python на iPhone не нужен. Нативный Objective-C++ порт выполняет detector,
weighted NMS, rotated crop, landmark/world projection, ROI tracking двух рук
и deduplication. Core ML разрешены CPU и Neural Engine; GPU сохраняется для
VRidge. Это разрешение устройств, не доказательство фактического размещения
каждой операции на ANE. Модели компилируются для iOS16+.

Числа скорости автора относятся к M4 и не являются результатами iPhone 16.
В CI выполняется сравнение геометрии/crop с pinned Python исходником, затем
нативного inference с его Python Core ML pipeline на обычном/зеркальном фото
и коллаже двух рук, по три последовательных кадра. Inference сравнивается
на macOS CPU_ONLY: это тест корректности, не аппаратный benchmark iPhone/ANE.
Различия интерполяции native crop и OpenCV допускаются и измеряются; bit-exact
эквивалентность всему pipeline не заявляется.

## Production 2.5

Build: bash ios/build.sh. Use scripts.package_ipa for a decrypted original IPA; scripts.update_injected_ipa for an already injected IPA. Both include the two compiled mlmodelc directories beside the dylib. Production preserves original bundle ID and URL schemes, removes obsolete .task assets and signatures. Input IPA is preserved. Signing and on-device verification remain separate. Proprietary IPA is excluded from git and CI.

Reference dependencies: OpenCV4.13.0.92, NumPy2.4.6, coremltools9.0. OpenCV5 changes warpAffine interpolation and is not this port's reference.
