# VRidge Hand Tracking Bridge 2.0 — MediaPipe

iPhone с задней ultra-wide камерой отслеживает обе руки в VRidge и отправляет
положение, ориентацию и скелет в Windows. ПК привязывает руки к шлему, фильтрует
движение, принимает Xbox 360 и передаёт контроллеры существующему
[GlassVR DaniXmir](https://github.com/DaniXmir/GlassVr). Собственный OpenVR-драйвер
не создаётся. Библиотека внедряется в VRidge, основной executable не заменяется.

**В 2.0 трекинг полностью переведён на MediaPipe. Захват — 640×480, 30 FPS.**
Apple Vision tracker, старый nonlinear 2D→3D solver, шаблон размеров кисти,
калибровка размеров и назначение «первая рука = правая» удалены из текущего кода.
Ручная центровка Back+Start сохранена. Старые версии доступны в истории Git.

## Установка готового релиза

1. Скачайте ZIP из [Releases](https://github.com/unc0ver1337/VRidge-HandTracking-Bridge/releases)
   и распакуйте **целиком** в отдельную папку. Python устанавливать не нужно.
2. Закройте старый Windows bridge. Запускайте только один bridge: GlassVR
   контроллеры общие. Не смешивайте EXE 1.x с IPA 2.0.
3. Установите `iOS/VRidge-HandTracking-2.0-Unsigned.ipa` совместимым способом
   с переподписью. IPA **unsigned**, нужны подходящие среда/подпись и разрешения
   Camera/Local Network. Bundle ID и URL schemes исходной IPA сохраняются.
   Обновление уже установленного VRidge зависит от bundle ID и выбранной переподписи.
4. GlassVR должен быть зарегистрирован в SteamVR и настроен на UDP. Если он уже
   установлен и работал с 1.x/экспериментом, переустановка драйвера не нужна.
   В ZIP сохранена прежняя исправленная DLL и патчи; она не изменена в 2.0 и не
   устанавливается автоматически. При ручной замене DLL сначала закройте SteamVR.
   Для первой установки драйвера используйте инструкции проекта GlassVR.
5. Телефон и ПК подключите к одной доступной локальной сети или точке доступа ПК.
   Запустите SteamVR и `Windows/Start-Bridge.cmd`, затем VRidge на iPhone.
   Сервер объявляется как GlassVR iPhone Bridge на всех IPv4-интерфейсах.
6. Если Firewall блокирует подключение, один раз запустите
   `Windows/Allow-Local-Network.ps1` от администратора: UDP39580 и mDNS5353,
   только локальные подсети. Изоляцию Wi-Fi клиентов и маршрутизацию скрипт
   обойти не может. Проверьте в консоли подключение телефона и packet loss.

Экспериментальный MediaPipe-клиент использует совместимый MPBR/v2, но для
полного обновления установите IPA основного релиза. Vision IPA 1.x несовместима.

## Центровка и Xbox 360

Держите контроллеры в удобном нейтральном направлении и **нажмите Back+Start**.
Пока комбинация удерживается, направление центрируется по текущей позе руки.
После отпускания поправка остаётся только до завершения bridge. Автоматических
центровок и сохранения индивидуального хвата нет; можно повторять по необходимости.

| Xbox 360 | Левый контроллер | Правый контроллер |
|---|---|---|
| LT / RT | LT — trigger | RT — trigger |
| LB / RB | LB — grip | RB — grip |
| Стики | Левый stick + LS | Правый stick + RS |
| Меню | X | Y |
| System | Back | Start |

Back+Start подавляет отдельные System-события до отпускания. A/B по умолчанию
не назначены; привязки редактируются в config.yaml. Оба контроллера отслеживаются
независимо. При отключении Xbox кнопки отпускаются. Стики передаются как Index
thumbsticks, не trackpads; действия меню зависят от SteamVR bindings игры.

## Где выполняется обработка

```text
iPhone ultra-wide 640×480 / 30 FPS
    → MediaPipe Hand Landmarker: 2 руки, handedness, 21 world landmarks
    → fit camera translation + palm quaternion на iPhone
    → MPBR/v2 UDP, latest frame only, clock sync / heartbeat
Windows: роли рук → HMD pose на момент кадра → фильтры → GlassVR → SteamVR
Xbox 360 → отдельный input loop ────────────────────────┘
```

MediaPipe работает в video mode на фоновой serial queue: занятый обработчик
пропускает кадр, очередь изображений не накапливается. Камера сохраняет native
sensor orientation без зеркалирования и поворотов вслед за интерфейсом.
При конфликте камеры VRidge получает приоритет; трекер приостанавливается.
Новых окон/панелей в iOS нет, только стандартные уведомления.

ПК не восстанавливает 3D через IK: он принимает готовую pose/21 joints.
Сторону задаёт MediaPipe; temporal association уменьшает смену ролей при flicker.
Положение и quaternion фильтруются отдельно; пальцы обрабатываются независимо.
Вырожденный сегмент одного пальца не убирает валидную позу контроллера:
до 350 мс удерживается его последняя достоверная поза, затем плавно используется
нейтральная. Такой палец помечается invalid, а не измеренным.

При исчезновении руки/потере связи tracking validity сбрасывается, устройства
GlassVR остаются подключёнными: это предотвращает повторное создание устройств.
После возвращения руки действует ограничение скачка/предсказания. HMD pose берётся
в RawAndUncalibrated, чтобы SteamVR применил room transform ровно один раз.

## Ограничения

World landmarks MediaPipe — оценка модели с центром у кисти, не абсолютные
измерения камерой глубины. Положение в camera space вычисляется на телефоне
из 2D/3D palm anchors и intrinsics с проверкой reprojection/cheirality.
Масштаб, окклюзии и ракурсы ребром оставляют неоднозначность. Depth sigma в
логах — эвристический нижний порог неопределённости, не измеренная ковариация.
Per-joint confidence модель здесь не даёт: points[:,2] обозначает availability.

По сети идут 21 точка 3D каждой руки. Текущий совместимый API GlassVR получает
pose + пять curls/пять splays и симулирует OpenVR skeleton. Независимое управление
всеми фалангами не заявляется. Реальные FPS, нагрев и задержка зависят от iPhone
и одновременного стриминга VRidge; 30 FPS — целевой захват, а не гарантия inference.

Пользователь подтвердил улучшение экспериментальной MediaPipe-версии. Это не
заменяет отдельную аппаратную проверку финального пакета 2.0 после установки.

## Исходники и сборка

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r pc/requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pc.bridge --config pc/config.yaml
```

Windows EXE: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`.
На Mac: `bash ios/build.sh`. SDK MediaPipe 1.1.1 и модель float16/v1 скачиваются
с проверкой pinned SHA256. Модель должна быть рядом с готовой dylib при упаковке.

Для исходной decrypted IPA: `python -m scripts.package_ipa --ipa private/original.ipa
--dylib artifacts/ios/VRidgeHandTracking.dylib --output artifacts/iOS/VRidge-HandTracking-2.0-Unsigned.ipa`.
Для уже инжектированной IPA используйте `scripts.update_injected_ipa` с теми же
аргументами: executable сохраняется побайтно. Подпись/profiles — отдельно;
package_ipa поддерживает identity/profile/entitlements на macOS. Проприетарная
IPA не коммитится и не передаётся в CI. В релиз она упаковывается локально.

GitHub Actions собирает ARM64 dylib и Windows EXE. `scripts.package_release`
проверяет согласованность IPA/dylib/model и формирует ZIP, BUILD.json и SHA256.
[Проверки и аппаратный checklist](docs/VALIDATION.md),
[wire protocol](docs/PROTOCOL.md), [лицензии/авторы](THIRD_PARTY.md),
[официальная документация MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/ios).
