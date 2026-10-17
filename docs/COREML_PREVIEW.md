# Core ML preview для iPhone 16 / iOS 18.5

Это отдельная тестовая ветка, рабочая 2.0 и её Release не заменяются.
Windows bridge 2.0 и GlassVR оставьте прежними. Меняется только iPhone backend.
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

## Что требуется от пользователя

1. Сохранить рабочую IPA 2.0 для возврата. Подписать тестовую IPA тем же доступным
   способом, сохраняя отдельный bundle ID com.riftcat.vridge2.coreml.preview.
   Сам файл unsigned. Название приложения — VRidge Core ML Test.
2. Разрешить Camera/Local Network. При необходимости заново настроить соединение
   VRidge с ПК в отдельном приложении. Запустить только один iPhone клиент.
3. Оставить текущий Windows bridge 2.0. Проверить VRidge stream, обе руки,
   повороты ладоней, сжатие кулака, центрирование удержанием Back+Start.
4. Через минуту посмотреть FPS/capture-to-output/packet loss в bridge.log;
   сравнить с 2.0 при тех же освещении/сети/нагрузке. Затем проверить нагрев
   за 10 минут. Первое открытие модели может занять больше времени на подготовку.
5. Сообщить: приложение запускается ли, видит ли обе руки, стороны/пальцы верны
   ли, что с задержкой и нагревом. При проблеме закрыть preview и вернуть 2.0.

Компьютер, SteamVR и приложение на телефоне при подготовке не запускаются.
Подпись/установка, фактическая работа ANE, реальные FPS и совместная работа с
VRidge на устройстве остаются аппаратной проверкой.

## Сборка

`bash ios/build.sh` скачивает модели/референс по неизменяемому commit и SHA256,
компилирует iOS модели и ARM64 dylib. Для тестов отдельно компилируются host
модели macOS. `scripts.package_coreml_preview` обновляет копию уже инжектированной
IPA: сохраняет executable, добавляет две mlmodelc директории, убирает старый
.task и подписи; задаёт отдельный bundle ID и убирает URL schemes стабильного
клиента. Проприетарная IPA в CI и git не загружается.

Для сравнения закреплены версии upstream: OpenCV4.13.0.92, NumPy2.4.6, coremltools9.0. OpenCV5 меняет интерполяцию warpAffine и не используется как эталон этой версии.
