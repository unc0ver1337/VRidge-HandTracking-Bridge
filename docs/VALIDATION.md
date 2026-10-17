# Проверки версии 2.5.1

62 Python-тестов: MPBR/v2, malformed/stale/reordered/lost packets, handshake,
clock sync, multi-adapter discovery, декодирование телефонной 3D pose,
оба semantic roles, flicker handedness, недопустимые quaternion/координаты,
исчезновение пальца и истечение hold, фильтры и reacquisition, Xbox mapping,
фиксированный хват, отсутствие центровки Back+Start, raw HMD transform, GlassVR wire/skeleton bounds, упаковка IPA.
Старый Vision solver и его тесты удалены. Synthetic Model находится только
в tests/geometry.py для тестовых данных; runtime её не импортирует.

Native C++ тест использует production TranslationFit.h: 980 синтетических поз
с поворотами, разными расстояниями и смещениями; NaN/вырожденные лучи/невалидные
intrinsics. Это тест математики, не оценка точности нейросети.

`python -m scripts.smoke_network` проверяет Bonjour + hello + clock sync +
synthetic 3D packet + GlassVR wire на loopback. SteamVR/камеру не запускает.
Loopback RTT нельзя принимать за задержку телефона.

CI собирает ARM64 dylib (ad-hoc codesign verify/load commands) и Windows EXE
(--help). Упаковка unsigned IPA проверяет executable, compiled models, dylib,
bundle ID и удаление прежних подписей. Это не проверка установки на iPhone.

Пользователь подтвердил улучшение Core ML preview на iPhone 16 / iOS 18.5.
Финальная 2.5.1 требует повторной аппаратной проверки:

1. Установить новую IPA, разрешить Camera/Local Network, запустить только новый bridge.
2. Проверить VRidge stream, discovery в обычной сети и точке доступа ПК.
3. Показать левую/правую руку и обе; проверить стороны при скрещивании.
4. Повернуть ладони к камере, от камеры, ребром; согнуть каждый палец/кулак.
5. Проверить приближение/удаление, вращение головы, сохранение хвата после перезапуска и независимые System Back/Start.
6. Убрать/вернуть руки, отключить/вернуть сеть и Xbox.
7. Проверить 10–15 минут: реальные FPS, capture-to-output с погрешностью clock
   sync, packet loss, rejected, нагрев. Сохранить bridge.log при сбое.

Сервер, SteamVR и VRidge при сборке/упаковке автоматически не запускаются.

CI additionally compares production CoreMLMath.h against pinned fasthands: 100 ROI cases and 16 image crops. Native CoreMLTracker inference is compared on macOS CPU_ONLY against upstream Python on original/mirrored photos and a two-hand collage, three frames each. This tests port parity, not model accuracy or iPhone/ANE speed. Measured JSON is included at iOS/library/coreml-parity.json in the release ZIP.

2.5.1: поправки обеих рук извлечены read-only из session_grip работающего bridge 2.5, повторное чтение дало те же значения. Тесты проверяют точное совпадение композиции с прежней сессией, сохранение положения/относительного вращения и независимые кнопки Back/Start. Финальный EXE 2.5.1 не запускался для аппаратного трекинга.
