# VRidge Hand Tracking Bridge

Две руки через ultra-wide камеру iPhone внутри VRidge → Windows → Knuckles в SteamVR.
Один Xbox 360 управляет кнопками обеих VR-рук одновременно.

**Основа SteamVR-интеграции — [GlassVR, автор DaniXmir](https://github.com/DaniXmir/GlassVr).**
Используются его OpenVR-драйвер, Index profile, UDP и скелетная анимация. Это не
новый самостоятельно написанный SteamVR-драйвер. Наш код: iOS Vision dylib,
discovery/протокол, реконструкция, фильтрация, привязка к HMD, Xbox mapping,
центровка и минимальный патч GlassVR для invalid-флага отключённых поз.

## Скачать и запустить

**[ZIP в Releases](https://github.com/vanyaponpon1337-web/VRidge-HandTracking-Bridge/releases)**
содержит Windows EXE с зависимостями, config, unsigned IPA, отдельную dylib,
исправленную DLL GlassVR и документацию.

**[Полный пошаговый туториал](docs/RELEASE_INSTALL.md)**

1. Установить SteamVR/VRidge и официальный GlassVR, включить два Index controller.
2. При выключенном SteamVR установить patched `GlassVR/driver_glassvr.dll`, сохранив
   оригинал. Выбрать UDP для position/rotation/input/skeletal обеих рук.
3. Полностью распаковать релиз и запустить `Windows/Start-Bridge.cmd`.
4. Установить IPA совместимым способом, разрешить Camera/Local Network, открыть
   VRidge. Телефон/ПК — одна LAN, Firewall должен пропускать bridge и mDNS.
5. Показать руки задней камере, проверить движения, кнопки и исчезновение рук.

**IPA unsigned:** для stock iOS нужна подходящая переподпись. iOS15+, ARM64 и
задняя ultra-wide камера обязательны. Исходная IPA предоставлена владельцем
проекта; её публичное включение в релиз подтверждено им отдельно. Сам VRidge
остаётся проприетарным приложением RiftCat.

Windows EXE не требует Python; `_internal` должен оставаться рядом. GUI GlassVR
устанавливается отдельно из upstream Releases. Наш bridge — консольное приложение;
внутри iOS дополнительные окна и панели не создаются.

## Возможности

* Vision: до двух рук, 21 landmark/confidence, camera intrinsics, capture timestamp.
* Ultra-wide, 640×480, capture60FPS при поддержке и адаптация к 30FPS.
* Bonjour, handshake, heartbeat, clock sync, reconnect, binary UDP ≤568 bytes.
* Sequence/loss/age checks и bounded latest-frame processing.
* Кинематическая модель с длинами костей, reprojection optimization,
  confidence/temporal priors и неопределённостью; фиксированный Z не используется.
* One Euro translation, quaternion filtering, ограниченное prediction.
* Raw OpenVR HMD pose: room transform применяется один раз.
* Два Index: pose/input, пять curls/splays → GlassVR 31-bone skeleton.
* Независимый Xbox input, deadzone, analog triggers, отпускание при отключении.
* Удержание Back+Start: постоянная центровка **курсоров** вперёд по HMD.
* Потерянная рука скрывается через 350ms и возвращается при tracking.
* Console FPS/latency/loss/reconstruction logs с ротацией.

## Xbox 360

Начиная с v1.0.1 обнаружение работает на всех локальных IPv4-адаптерах, включая
точку доступа Windows, с проверкой новых интерфейсов каждые 5 секунд.
Оставьте `advertise_ip: null` и `bind_ip: 0.0.0.0` для автоматического режима.
Подробнее: [Wi-Fi, Ethernet и hotspot](docs/NETWORK_INTERFACES.md).

| Xbox | Действие |
|---|---|
| X / Y | B левого / правого Index — меню по bindings игры |
| Back / Start отдельно | System левой / правой руки |
| LT / RT | Analog trigger левой / правой руки |
| LB / RB | Grip левой / правой руки |
| Левый / правый стик | Thumbstick соответствующей руки |
| LS / RS click | Thumbstick click |
| Back + Start удерживать | Постоянно центрировать курсоры вперёд |

Центровка сохраняет позиции и задаёт нейтральную ориентацию. Результат записывается
в `orientation.local.yaml`; его загрузка описана в туториале. A/B Xbox свободны.
Меню через B определяется игрой. Нажимайте сочетание вместе: отдельная кнопка,
нажатая раньше второй, может успеть отправить System.

## Проверки и ограничения

Владелец проверял iPhone→Windows и контроллеры на реальном оборудовании.
После патча проверены реальные OpenVR connected/valid flags. Локально проходят
47 автоматических тестов. Результаты сборки EXE и CI приведены в release notes.
Не заявляем измеренную полную display latency, независимую ground-truth точность,
совместимость со всеми играми или длительный аппаратный soak test.

Монокулярная RGB-камера не даёт однозначный 6DoF при всех ракурсах. Окклюзии,
edge-on ладонь, crossing и быстрые движения могут давать ошибки ориентации,
identity или отклонённые позы. Нужна калибровка ладони, линзы и крепления к HMD.
Скелет GlassVR приближённый: независимые 3D-joint poses не передаются.
Haptics обратно к Xbox отсутствуют. 30–60FPS всего pipeline не гарантированы.

Патч DLL нужен для invalid-флага потерянной руки; официальная переустановка
GlassVR может его перезаписать. Bridge управляет enable flags GlassVR — не
переключайте их одновременно вручную.

## Сборка из исходников

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r pc\requirements.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pc.bridge --config pc\config.yaml
powershell -File scripts\build_windows.ps1
```

macOS/Xcode: `bash ios/build.sh`. Упаковка собственной расшифрованной IPA:

```powershell
python scripts/package_ipa.py --ipa original.ipa --dylib VRidgeHandTracking.dylib --output private/VRidge-Unsigned.ipa
```

Упаковщик добавляет LC_LOAD_DYLIB в проверенное свободное место заголовка,
библиотеку и metadata разрешений. Основной код VRidge не заменяется. Signing
на macOS описан в технической истории; сертификаты и profiles в Git не входят.

* [Пошаговая установка и диагностика](docs/RELEASE_INSTALL.md)
* [Протокол](docs/PROTOCOL.md)
* [Патч драйвера и проверка](docs/DRIVER_VISIBILITY_FIX.md)
* [Центровка и видимость](docs/LIVE_CENTER_AND_VISIBILITY.md)
* [HMD/raw координаты](docs/HEAD_RELATIVE_FIX.md)
* [Историческая архитектура и первоначальные проверки](docs/ARCHITECTURE_HISTORY.md)
* [Атрибуция GlassVR, VRidge и зависимостей](THIRD_PARTY.md)

MIT распространяется на наш код, а не на сторонние приложения и библиотеки.
