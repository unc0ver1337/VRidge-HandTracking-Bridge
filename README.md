# VRidge Hand Tracking Bridge

Отдельная Objective-C++ библиотека для VRidge 2.7.8 и Windows Python bridge к существующему GlassVR. Исходный исполняемый код VRidge сохраняется; упаковщик добавляет `LC_LOAD_DYLIB` в проверенное свободное место заголовка Mach-O. Отдельного SteamVR-драйвера и дополнительного окна в VRidge нет.

**Статус: реализация, автоматизированные проверки и сборка dylib доступны. Сквозная аппаратная работоспособность ещё не подтверждена.** Нет доступного подключённого iPhone/Xbox; SteamVR при проверке вернул `Init_NoServerForBackgroundApp`. Подписанная IPA не создана: сертификат, подходящий provisioning profile и среда установки не предоставлены. Локальная IPA с внедрением создана как **UNSIGNED**, а не как проверенный устанавливаемый пакет. См. [результаты проверок](docs/VALIDATION.md).

## Устройство системы

```text
Ultra-wide AVFoundation → centre-crop/scale 640×480 → Vision (до 2 рук)
   → Bonjour discovery + nonce/session handshake + NTP-like clock sync
   → binary UDP ≤568 bytes → latest-frame receiver → identity association
   → constrained kinematic reprojection solve → uncertainty + world-space filter
   → camera-to-HMD mount + capture-time OpenVR HMD pose → GlassVR UDP
Xbox 360 XInput → independent 10 ms input thread → GlassVR UDP
```

Границы модулей: `ios/Tracking`, `ios/Network`, `pc/network.py`, `pc/reconstruction`, `pc/tracking`, `pc/controller`, `pc/glassvr`. Ошибка одной руки не останавливает вторую; ошибки SteamVR и XInput изолированы от сетевого приёма. Сетевая очередь содержит только последний кадр; iOS допускает одну Vision inference и один исходящий пакет одновременно. Поздние результаты отбрасываются. Логи вращаются: 8 MB × 4 файла.

## Быстрый запуск Windows

Требования: Windows 10/11 x64, Python 3.12+, SteamVR, VRidge, GlassVR; iPhone с задней ultra-wide камерой и iOS 15+. Реальные 60 FPS зависят от формата камеры, Vision, температуры и скорости ПК.

1. Установите GlassVR из [официального проекта](https://github.com/DaniXmir/GlassVr). Используйте его установку драйвера; не заменяйте HMD VRidge эмулированным HMD GlassVR.
2. В GlassVR включите оба Index controller, назначьте **position, rotation, input и skeletal = UDP** для каждой руки. Порт левой руки `9001`, правой `9002`. Отключите другие источники тех же каналов. Изменения конфигурации драйвера могут требовать перезапуска SteamVR.
3. При совместном использовании драйверов установите `steamvr.activateMultipleDrivers: true` в `steamvr.vrsettings`, предварительно сохранив копию файла. Настройка относится к секции `steamvr`, а не к произвольной секции драйвера.
4. Измерьте ладонь и крепление камеры; заполните `pc/config.yaml` по разделу калибровки ниже. Bridge получает HMD в `RawAndUncalibrated` и передаёт GlassVR raw driver poses; SteamVR применяет преобразование игровой зоны один раз. Для пользовательской диагностики используется `Standing`.
5. Запустите `start-windows.cmd`. Первый запуск создаёт venv и устанавливает зависимости. Альтернативно:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r pc\requirements.txt
.venv\Scripts\python -m pc.bridge --config pc\config.yaml
```

6. Разрешите Python входящий UDP `39570` и mDNS `5353` **в частной сети** в Windows Firewall. Телефон и ПК должны находиться в одной сети без AP/client isolation. При VPN или нескольких интерфейсах укажите Wi-Fi IPv4 ПК в `network.advertise_ip`; IP телефона вводить не требуется.
7. Установите совместимо подписанную/подготовленную IPA и запустите VRidge. Разрешите локальную сеть, камеру и уведомления. Сервер показывает имя устройства и адрес. Должны появиться состояния поиска, найденного ПК, подключения и запуска трекинга.
8. Запустите `python -m scripts.verify_steamvr`: этот скрипт читает реальные роли, serial, connected/valid pose и controller input state. Ненулевой exit code означает, что аппаратная проверка не пройдена. Затем проверьте движение и кнопки в SteamVR Input Debugger; доступный state сам по себе не доказывает, что он обновляется.

`Ctrl+C` освобождает кнопки обеих рук, останавливает потоки и снимает Bonjour-объявление. `--duration 10` запускает ограниченную диагностику с тем же реальным сервером.

## iOS: сборка и внедрение

На macOS с Xcode/iPhoneOS SDK:

```bash
bash ios/build.sh
```

Результат: `ios/build/VRidgeHandTracking.dylib`, ARM64, минимальная версия dylib iOS 15.0, Apple Vision/AVFoundation/CoreImage/UserNotifications, ad-hoc signature. **Ad-hoc signature библиотеки не является developer-подписью приложения.** GitHub Actions `Build and test` собирает и проверяет dylib на `macos-15`, запускает тесты на Windows и сохраняет только нашу библиотеку/отчёты. Проприетарная IPA в этот workflow не поступает.

Локальная упаковка на Windows/macOS:

```powershell
python scripts/package_ipa.py --ipa "C:\path\com.riftcat.vridge2_2.7.8_und3fined.ipa" --dylib "artifacts\VRidgeHandTracking.dylib" --output "private\VRidge-HandTracking-Unsigned.ipa"
```

Упаковщик проверяет ARM64, расшифровку, размеры команд и нулевое свободное место перед секциями. При нехватке места отказывается изменять бинарник. Код и смещения секций не переписываются. Добавляет библиотеку в `Frameworks`, `VHBridge.plist`, camera/local-network descriptions и `NSBonjourServices = [_vhbridge._udp]`. Сохраняет bundle ID, исходные frameworks, ресурсы и entry point; удаляет устаревшие signature references и provisioning profile. Минимальная версия результирующей IPA повышается до iOS 15, соответствуя dylib; оригинальная IPA остаётся без изменений. Повторное внедрение отклоняется.

**Unsigned IPA не устанавливается обычным способом на stock iOS.** Нужна поддерживаемая среда инжектирования/установки или полноценная переподпись; конкретная совместимость jailbreak/TrollStore зависит от версии iOS и здесь не проверена. Мы не устанавливаем приватные entitlements и не обходим проверку подписи. Разрешение `com.apple.developer.networking.multicast` не требуется для системного Bonjour browse; raw broadcast/multicast не используется.

На macOS с корректными developer signing materials:

```bash
python3 scripts/package_ipa.py --ipa /private/original.ipa \
  --dylib ios/build/VRidgeHandTracking.dylib --output private/VRidge-Signed.ipa \
  --identity 'Apple Development: Your Name (TEAMID)' \
  --profile /private/matching.mobileprovision --entitlements /private/app-entitlements.plist
```

Profile должен разрешать **сохранённый bundle ID** и устройство; `application-identifier` в entitlements должен совпадать. Все вложенные frameworks/dylibs подписываются до приложения; затем выполняется `codesign --verify --deep --strict`. Дополнительные capabilities исходного VRidge должны разрешаться profile. Полная семантическая совместимость entitlements и установка проверяются на устройстве — `codesign` не заменяет эту проверку.

Workflow `Private local-host IPA packaging` использует только ваш **self-hosted macOS runner с меткой `vridge-private`**, локальные пути к IPA/profile/entitlements и GitHub Secret `IOS_SIGN_IDENTITY`. Сертификат с private key должен быть заранее импортирован в защищённый keychain этого runner. IPA остаётся локально в `private/`, её upload отсутствует. Job разрешён только для private repository. Никогда не добавляйте IPA, сертификаты, provisioning profiles или содержимое VRidge в Git/Release/публичные артефакты. Локальный `.gitignore` исключает их, но не заменяет проверку перед публикацией.

### Поведение твика

Камера запускается только после handshake. Поиск ограничен 15 секундами; затем освобождаются ресурсы и через 5 секунд начинается новое ограниченное окно поиска. Потеря heartbeat на 3 секунды останавливает capture; восстановление соединения запускает его снова. Приложение принудительно не завершается.

Твик наблюдает lifecycle capture sessions VRidge и уступает камеру оригинальному приложению; чужие sessions не останавливает и не модифицирует. Runtime camera errors приводят к освобождению собственной session и повторной попытке через 5 секунд. Обычные interruptions ждут системного resume. **Это безопасная политика fallback, но фактическая одновременная работа камеры и стриминга VRidge требует проверки на iPhone.** Уже работающая до регистрации наблюдателей чужая session может не быть известна твiku; обработка interruptions остаётся резервным механизмом.

Уведомления — стандартные локальные banner без звука, без GUI/overlay. Делегат пересылает посторонние события предыдущему делегату VRidge. Они требуют разрешения пользователя, учитывают Focus и могут быть скрыты системой/настройками. Те же состояния всегда идут в device log с префиксом `VH`. Камера и уведомления могут вызвать стандартный системный запрос разрешения при первом запуске.

`ios/VHBridge.plist`: Width/Height, FPS (30/60), DiscoveryTimeoutSeconds. Внешний формат камеры выбирается по близости к целевому разрешению и реальной поддержке FPS; CoreImage сохраняет пропорции при центральном crop/scale. Результат Vision и intrinsics относятся к **одному и тому же** 640×480 изображению. После 120 inference при среднем времени >25 ms capture понижается до 30 FPS. Главный поток не выполняет capture или Vision.

## Реконструкция и точность

Кинематическая модель содержит translation (3), rotation vector (3), пять наборов `[splay, MCP, PIP, DIP]` (20). Quaternion используется для результата/фильтра; rotation vector — удобная локальная параметризация оптимизации. MCP anchors образуют жёсткую ладонь, сегменты пальцев сохраняют заданные длины. Левой руке соответствует отражение геометрии локальной модели, а не отражённая quaternion.

Минимизируется confidence-weighted reprojection residual, слабое ограничение согласованности PIP/DIP, temporal prior translation/SO(3)/angles, штраф выхода за camera plane и слабый winding cue palm facing. `least_squares`, robust `soft_l1`, анатомические bounds. Начальная глубина получается из измеренной ширины ладони и углового расстояния между MCP; начальная ориентация — из palm axes. При повторном появлении решаются две стартовые гипотезы наклона; это **не исчерпывающий поиск всех монокулярных неоднозначностей**. Частично скрытые суставы восстанавливаются моделью/историей; при недостатке уверенных palm points рука отклоняется.

Jacobian вычисляется central differences сразу для всех 26 параметров в vectorized NumPy, с ограниченным числом итераций: 22 при старте, 8 на последовательных кадрах. Сильная окклюзия/быстрое движение могут потребовать больше; увеличивайте budget только после измерения FPS. Тяжёлые нейросети/MediaPipe не нужны: landmarks уже получены Vision. SciPy/NumPy достаточно для решателя; OpenCV нужен только для опциональной offline калибровки. Kalman не используется, поскольку One Euro даёт более простой управляемый speed-dependent отклик без ложной уверенности в модели ускорений.

Передаются и учитываются confidence, capture host timestamp, sequence, version, session, dimensions, intrinsics, chirality и слабый palm/back cue. Масштаб ладони, wrist position и направление пальцев однозначно вычисляются из переданных landmarks без дублирования полей. Palm normal, toward/away/edge, reprojection error и depth uncertainty выводятся на ПК. Winding около edge-on подавляется. **Ориентация всегда помечается ambiguous:** малый reprojection error не доказывает правильность скрытой глубины, полного 180° разворота или axial roll.

После оптимизации оценивается локальная covariance из Jacobian. Для глубины действует минимум 15% оценки Z, поскольку шаблон и масштаб могут ошибаться; это консервативная эвристика, **не эмпирически откалиброванный доверительный интервал**. Персональная калибровка не снимает все неоднозначности. Фиксированного Z для каждого landmark нет: flexion меняет их глубину по кинематической цепочке.

### Калибровка

1. Измерьте расстояние index-MCP → little-MCP в метрах и задайте `reconstruction.palm_width_m`. Шаблон segment lengths — ориентир взрослой руки, а не точная антропометрическая модель каждого пользователя; можно задать свои пять строк `bone_lengths_m`.
2. Опциональная кнопка Start оценивает масштаб по frontal ладони на заранее измеренной **глубине вдоль оптической оси** `calibration_distance_m`. Держите пальцы расправленными. Результат сохраняется в `pc/calibration.local.yaml`; для последующих запусков явно используйте `--config pc/calibration.local.yaml`. Косой ракурс и неправильное расстояние дают ошибку масштаба — предпочтительнее прямое измерение ладони.
3. Capture intrinsics берутся из attachment AVFoundation, преобразуются тем же scale/crop. При отсутствии attachment используется FOV estimate, отмеченный флагом. Ultra-wide distortion нельзя считать нулевым просто из наличия K: нужна калибровка **того же capture format/crop/разрешения** и понимание системной lens correction.
4. Для Brown–Conrady offline калибровки установите `opencv-python` и снимите ≥10 разнообразных шахматных кадров из точно такого же capture pipeline. Команда: `python -m scripts.calibrate_camera --columns 9 --rows 6 --square-m 0.024 image1.png ...`. Перенесите `intrinsics`, `distortion` в config. Этот инструмент не извлекает изображения из Vision-пакетов: они содержат только landmarks. Для fisheye, который плохо описывается Brown–Conrady, такой calibration fit непригоден — проверьте RMS и края изображения; потребуется отдельная калибровка/модель линзы.
5. Измерьте camera centre относительно tracked HMD origin и mount rotation, задайте `space.camera_offset_m` и `camera_rotation_deg`. Native sensor coordinates фиксированы, unmirrored: X вправо, Y вниз, Z вперёд. UI autorotation не меняет видеобуфер и coordinates. Базис OpenVR: X вправо, Y вверх, Z назад; `diag(1,-1,-1)` — proper rotation. Не дублируйте его в mount correction.
6. `space.mode: hmd` использует capture-time историю HMD и SLERP; без свежей реальной HMD pose world outputs подавляются. Для физически неподвижной камеры допускается `static` с измеренной origin. **Для телефона в движущемся шлеме static недопустим.** `rigid_alignment` предоставляет Kabsch fitting для ≥3 неколлинеарных пар 3D correspondence, если такие измерения доступны.
7. Настройте `grip_rotation_deg` отдельно для сторон, сверяя Index model и SteamVR pointing ray с рукой. Нулевые offsets — исходная настройка, **не универсальная доказанная ориентация Index grip**. Back сбрасывает temporal estimates; глобальное центрирование tracking universe выполняется штатной функцией SteamVR.

One Euro translation настраивается отдельно от angular-speed SLERP. Quaternion signs согласуются, prediction translation ограничен 30 ms/3 cm. Реальное prediction по умолчанию 15 ms. При потере руки pose перестаёт обновляться, через 350 ms кнопки отпускаются. При возврате ограничены скорость перехода (1.5 m/s) и angular speed (6 rad/s). **GlassVR UDP не предоставляет valid/disconnected flag**, поэтому драйвер может показывать замороженную руку как tracked. Мы не выдаём frozen pose за новое измерение и не отправляем руку в произвольную далёкую точку.

Сопоставление двух рук использует semantic chirality, wrist velocity, глобальное назначение Hungarian и retention 0.7 s. Crossing/небольшие пропуски покрыты тестами, но полное перекрытие и неразличимые руки могут оставить identity ambiguous. Гарантировать отсутствие swaps во всех случаях RGB не позволяет.

## Xbox 360: один геймпад

| Кнопка | Действие |
|---|---|
| LB / RB | Выбрать руку для кнопок |
| RT / LT | Analog trigger / grip выбранной руки |
| A / B | Primary / secondary |
| X | Thumbstick click |
| Y | Переключить split sticks ↔ stick выбранной руки |
| Left Stick | Левый VR thumbstick (обычно движение) |
| Right Stick | Правый VR thumbstick (обычно поворот) |
| Start | Персональная калибровка на измеренной глубине |
| Back | Сброс временного состояния; world recenter через SteamVR |
| D-pad Up | System выбранной руки |

Все назначения кнопок, trigger source, deadzone и XInput index заданы в YAML. Игра определяет смысл осей через bindings SteamVR. По умолчанию sticks доступны обеим рукам одновременно независимо от выбора кнопок; camera tracking также всегда независим. При смене руки прежние кнопки освобождаются. При отключении pad отправляется neutral input, thread продолжает обнаружение. Haptics обратного направления не реализованы: выбранный UDP API GlassVR передаёт input/pose/skeleton в одну сторону.

## GlassVR совместимость

Изучен upstream commit `4d530752a52febb39a3cb9ade3632e4c2ce77425`: [UDP example](https://github.com/DaniXmir/GlassVr/blob/4d530752a52febb39a3cb9ade3632e4c2ce77425/examples/python/udp%20index%20controller.py), [packed structures](https://github.com/DaniXmir/GlassVr/blob/4d530752a52febb39a3cb9ade3632e4c2ce77425/code-glassvrdriver/HmdVr/globals/packets.h), [receiver](https://github.com/DaniXmir/GlassVr/blob/4d530752a52febb39a3cb9ade3632e4c2ce77425/code-glassvrdriver/HmdVr/globals/comm.cpp), [skeletal simulation](https://github.com/DaniXmir/GlassVr/blob/4d530752a52febb39a3cb9ade3632e4c2ce77425/code-glassvrdriver/HmdVr/devices/hand_simulation.cpp).

Используется loopback UDP — подключение без блокирующего создания четырёх Named Pipes на каждую руку. `P: <c3d` (25 bytes), `R: <c4d` wxyz (33), `I: <c12?8d` (77), `S: <c25d` (201). Little-endian, без native padding. Upstream использует пять общих curls: flexions 0,4,8,12,16; прочие 15 слотов игнорируются. Curl fitted к реальным upstream angular gains; splay units: 20° thumb, 15° остальные. Драйвер генерирует 31-bone skeleton из этих десяти значений. **Передача независимой 3D rotation каждого finger joint этим интерфейсом не поддерживается**, хотя локальный решатель оценивает MCP/PIP/DIP отдельно. Новый собственный драйвер/патч GlassVR не нужен для этих каналов.

## Тесты и диагностика

```powershell
python -m pytest -q
python -m scripts.smoke_network
python -m scripts.benchmark --frames 120
python -m scripts.verify_steamvr
```

Smoke использует реальный Bonjour/UDP loopback и **явно синтетическую** руку; он не доказывает iPhone/SteamVR tracking. Тесты покрывают wire roundtrip/validation, sequence wrap/loss/reorder, session/age, clock handshake, bounded queue, scalar/vectorized FK agreement, exact bone lengths, relative depths, left/right, rotated palm projection, occlusion rejection, distortion inversion, rigid calibration, quaternion sign/normalization, adaptive filtering/reacquisition, crossing/loss identity, XInput mapping/switch/disconnect и точные upstream packet sizes/units + actual UDP sink. Подробности: [docs/VALIDATION.md](docs/VALIDATION.md), [docs/PROTOCOL.md](docs/PROTOCOL.md).

Console FPS — число принятых обработанных кадров, не сенсорный FPS Vision. Latency — capture→выход bridge, с оценкой clock RTT; она **не включает driver→render→display**. Packet loss оценивается по пропущенным sequence; поздние пакеты/reordering и latest-frame replacement выводятся отдельно. Монокулярная неопределённость, проблемные poses и отсутствие HMD также видны в логах.

## Аппаратная приёмка

1. Сделать резервную копию VRidge. Проверить подпись, установку, launch, исходный streaming/звук/настройки без сервера и с ним.
2. Проверить deny/grant camera/local-network/notifications, ultra-wide-only выбор, 640×480, 30/60 FPS и thermal throttling по device logs.
3. Открыть QR camera VRidge во время tracking: streaming не должен падать, tracker должен уступить и затем восстановиться. Проверить background/foreground и входящий звонок.
4. Проверить имя Bonjour, два телефона/сервера, Wi-Fi reconnect, 15 s discovery timeout, выключение bridge и 3 s heartbeat timeout. Не использовать результаты loopback как доказательство LAN compatibility.
5. На известных расстояниях/углах измерить ошибку position и orientation: ладонь/тыльная сторона, edge-on, roll 180°, пальцы согнуты, crossing и полное перекрытие. Сравнить с внешним tracking reference/физическими метками; сохранить uncertainty отдельно.
6. В SteamVR подтвердить обе роли Index, реальное обновление pose и input, pointing direction, правильность координат при движении головы и руками. Проверить потери рук и отпускание input; frozen-tracked ограничение GlassVR учитывать явно.
7. Подключить единственный Xbox, проверить выбор руки, split sticks, analog triggers, hot-unplug, Start/Back и реальные игровые bindings.
8. Измерить end-to-end latency камерой/внешним эталоном и минимум 30 минут проверить стабильность памяти, нагрузки/температуры и Wi-Fi. До этих шагов проект нельзя считать завершённой аппаратно подтверждённой VR-системой.

Лицензия собственного кода: MIT. VRidge и GlassVR принадлежат их авторам; исходная IPA и сторонний драйвер в этом репозитории отсутствуют.
