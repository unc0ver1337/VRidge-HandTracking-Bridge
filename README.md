# VRidge Hand Tracking Bridge 2.6 — MobRecon

Трекинг двух рук камерой iPhone внутри VRidge с передачей положения, ориентации и пальцев в SteamVR через Windows и GlassVR. **640×480 / 30 FPS capture**, задняя ultra-wide камера. Пользователь подтвердил существенное улучшение экспериментальной версии MobRecon; этот backend перенесён в основной проект без изменения модели и её параметров.

## Что изменилось

**Настоящий MobRecon DenseStack + SpiralConv** заменил 3D-модель MediaPipe. Apple Vision используется только для поиска рук, определения стороны и подготовки 2D ROI. Восстановление 3D выполняет обученный MobRecon, затем поза переводится в существующий MPBR/v2. Старые MediaPipe модели в новую IPA не включаются.

Сохранены две руки, сетевое обнаружение, HMD-relative tracking, независимые фильтры положения/вращения/пальцев, Xbox mapping и фиксированный хват из 2.5.1. Ручная центровка **не возвращена**: Back+Start не меняет направление. Жестов для кнопок нет. GlassVR-драйвер остаётся прежним.

## Авторы и основа

- **[Xingyu Chen и соавторы — MobRecon / HandMesh](https://github.com/SeanChenxy/HandMesh)**: обученная 3D-модель и mesh pipeline, официальный SpConv checkpoint.
- **[DaniXmir — GlassVR](https://github.com/DaniXmir/GlassVr)**: эмуляция Index/OpenVR pose, input и skeleton.
- **[Vimal Mollyn — fasthands / Core ML port](https://github.com/VimalMollyn/Mediapipe-Hands-PyTorch-CoreML)**: основа прежнего backend 2.5; благодарность и лицензия сохранены в истории и third_party. В 2.6 этот inference backend не используется.
- Интеграция iPhone/VRidge/Windows — unc0ver1337. VRidge принадлежит RiftCat.

Лицензии и ограничения сторонних компонентов: [THIRD_PARTY](THIRD_PARTY.md).

## Установка готового релиза

1. Скачайте ZIP **[2.6.0 из Releases](https://github.com/unc0ver1337/VRidge-HandTracking-Bridge/releases/tag/v2.6.0)** и распакуйте полностью. Python не требуется. Не отделяйте Windows EXE от папки `_internal`.
2. Закройте старый bridge. Установите `iOS/VRidge-HandTracking-2.6.0-Unsigned.ipa` своим совместимым способом с переподписью. IPA **unsigned**, требуется iOS16+ и задняя ultra-wide камера. Для iPhone16/iOS18.5 подходит целевая платформа сборки; финальную установку проверяет пользователь.
3. Это основной VRidge-клиент: bundle ID и URL schemes исходной основной IPA сохраняются. Приложение называется **VRidge Hand Tracking 2.6**. Тестовый VRidge MobRecon Test имеет другой ID и не заменяется автоматически. Не запускайте два клиента одновременно.
4. Разрешите Camera/Local Network, настройте обычный VRidge stream как прежде.
5. Если GlassVR уже работает с проектом, переустановка драйвера не нужна. При первой установке следуйте [инструкции GlassVR](https://github.com/DaniXmir/GlassVr), зарегистрируйте драйвер в SteamVR и включите UDP обоих контроллеров. В ZIP лежат прежняя DLL и минимальные патчи; автоматической установки нет. DLL меняйте только при закрытом SteamVR. [Подробности драйвера](docs/DRIVER_VISIBILITY_FIX.md).
6. Подключите телефон и ПК к доступной друг другу локальной сети, запустите SteamVR, `Windows/Start-Bridge.cmd`, затем VRidge на iPhone. Один bridge и один клиент одновременно. Windows 2.5.1 также совместим; в комплект включён пересобранный 2.6.0.
7. При блокировке сети выполните `Windows/Allow-Local-Network.ps1` от администратора. Он разрешает UDP39580 и mDNS5353 для локальных подсетей. Discovery объявляет GlassVR iPhone Bridge на IPv4-интерфейсах; точка доступа ПК работает при доступной маршрутизации. Изоляцию Wi-Fi клиентов firewall-правило не обходит.

Проверьте телефон, FPS, packet loss и rejected в консоли. Завершение bridge — Ctrl+C. Сохраните предыдущий рабочий релиз для возврата.

## Xbox 360 и фиксированный хват

| Xbox | Левый контроллер | Правый контроллер |
|---|---|---|
| Trigger | LT | RT |
| Grip | LB | RB |
| Thumbstick / click | левый stick / LS | правый stick / RS |
| Menu | X | Y |
| System | Back | Start |

Back и Start — обычные System-входы, включая одновременное нажатие. A/B Xbox по умолчанию не назначены. Стики передаются как Index thumbsticks, не trackpads. Привязки и deadzone — в `Windows/config.yaml`; действия также зависят от SteamVR bindings игры. При отключении Xbox кнопки отпускаются. Input подавляется для руки без недавней валидной позы.

Хват обеих рук фиксирован точно как в 2.5.1. Нет ручной/автоматической центровки и загрузки сохранённых профилей. [Происхождение поправок и ограничения](docs/FIXED_GRIP.md). Замена модели может менять её оценку позы; поправка хвата не устраняет ошибки самой модели.

## Обработка

```text
iPhone ultra-wide 640×480 / 30 FPS capture
  → Vision 2D ROI + chirality, до двух рук
  → upright crop, canonical mirror левой руки
  → MobRecon Core ML: mesh decoder → 21 world joints + 2D joints
  → undo rotation/mirror → camera translation fit + palm quaternion
  → MPBR/v2 UDP, timestamps, sequence, heartbeat / clock sync
Windows → hand identity → HMD pose at capture → filters → GlassVR → SteamVR
Xbox → отдельный input loop ───────────────────────────────┘
```

Положение, ориентация и пальцы обрабатываются отдельно. Занятый обработчик пропускает кадр: очередь изображений не накапливается. Захват сохраняет native sensor orientation без зеркалирования интерфейсом. При конфликте камеры трекер уступает VRidge. Новых окон/панелей внутри iOS нет, только системные уведомления.

Хват/положение привязаны к HMD на момент кадра. HMD берётся в RawAndUncalibrated, чтобы SteamVR применил room transform ровно один раз. При потере руки tracking validity сбрасывается; устройства GlassVR остаются подключёнными. Невалидный палец удерживается кратковременно, затем используется нейтральная поза. По сети идут 21 сустав на руку; совместимый GlassVR API получает пять curls и пять splays для симуляции skeleton, не независимые повороты всех фаланг.

## Скорость, точность и ограничения

Экспорт **FP32** сохранён из проверенной пользователем версии: FP16 не прошёл выбранный допуск PyTorch/Core ML parity. Core ML разрешены CPU + ANE, GPU оставлен VRidge. Это не доказательство фактического размещения операций на ANE. **30 FPS — захват, а не гарантированный inference FPS**; скорость и нагрев зависят от телефона, двух рук и одновременного VRidge stream.

Модель восстанавливает приблизительную 3D-кисть из RGB, не измеряет глубину. Масштаб/перекрытия/ракурсы ребром остаются неоднозначными. Vision может потерять ROI; MobRecon может ошибаться с объектами в руках. Улучшение preview подтверждено пользователем, но объективные метрики точности/FPS и финальную 2.6 нужно проверять отдельно. [Проверки](docs/VALIDATION.md).

## Сборка исходников

Windows/Python: `python -m pip install -r pc/requirements.txt`, `python -m pytest -q`, `python -m pc.bridge --config pc/config.yaml`. EXE: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`.

macOS + Xcode + Python3.11:

```sh
python -m pip install torch==2.7.1 coremltools==9.0 numpy==1.26.4 scipy==1.15.3 opencv-python-headless==4.11.0.86 gdown==5.2.0
bash ios/build.sh
python tests/native_mobrecon_smoke.py
```

Веса официального MobRecon скачиваются публично, проверяются по SHA256. Публичный source commit и topology hashes — `models/upstream.json`. Модель/референс не зависят от временного приватного репозитория. CI собирает iOS/Windows и проверяет 65 Python tests, ROI/crop/mirroring, 980 synthetic translations, PyTorch/Core ML parity и нативный pipeline с двумя руками.

Рядом с dylib при упаковке должна находиться `mobrecon.mlmodelc`. Для исходной decrypted IPA используйте `python -m scripts.package_ipa --ipa private/original.ipa --dylib ios/build/VRidgeHandTracking.dylib --output artifacts/VRidge-HandTracking-2.6.0-Unsigned.ipa`. Для уже инжектированной IPA — `scripts.update_injected_ipa` с теми же аргументами: executable сохраняется побайтно, старые модели/подписи заменяются. macOS signing поддерживает identity/profile/entitlements с проверкой bundle ID. Проприетарная IPA, сертификаты и signing secrets исключены из git/CI; релиз упаковывается локально.

Основной код MIT; сторонние модели, MANO-производные assets, драйвер и VRidge сохраняют собственные условия. Не переносите условия MIT нашего кода автоматически на весь ZIP.
