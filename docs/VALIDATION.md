# Проверки — 13 октября 2026

## Подтверждено

| Проверка | Результат и граница доказательства |
|---|---|
| Исходная IPA | Найдена на Desktop, VRidge 2.7.8 build18, thin ARM64, основной Mach-O `cryptid=0`; оригинал не изменён |
| iOS build | [CI 38429820870](https://github.com/vanyaponpon1337-web/VRidge-HandTracking-Bridge/actions/runs/38429820870): macOS ARM64 dylib, ad-hoc codesign verification, load commands, artifact upload — success; предупреждений clang не найдено |
| Python CI | В том же CI Windows/Python3.12: 39 tests success. Дополнительный packaging regression добавлен после этого run; актуальные runs доступны в Actions |
| Локальные тесты | **40 passed in 2.56 s**, Windows11/Python3.14; JUnit в локальном `artifacts/test-results-local.xml` |
| Реальный Bonjour/UDP | `python -m scripts.smoke_network`: discovery, hello/welcome, clock sync, binary frame, solver, actual loopback GlassVR-wire sink — PASS; источник landmarks явно синтетический |
| Размеры GlassVR packets | P25, R33, I77, S201 bytes, порядок wxyz, curl и splay conversion проверены |
| Server без телефона | Реально объявлен на LAN IPv4, console waiting, XInput отсутствует; ограниченный запуск завершён с освобождением ресурсов |
| IPA packaging | Локально создана unsigned IPA с dylib и Bonjour/camera metadata. Все байты основного executable с offset16384 до конца совпали с оригиналом. Установка не проверена |
| Утечки proprietary content | IPA исключены из Git; private packaging workflow не загружает IPA в artifacts. Собственный source zip также не содержит IPA |

Контрольные суммы локальных финальных iOS-артефактов:

```text
VRidgeHandTracking.dylib
d99c6d7c7050484114fbea1c6438a4e300fb9bb30a6f3245eebcf730c9b2c5b2

VRidge-HandTracking-Unsigned.ipa
cf395890980dfe674ff22b756bca1ce4304ca83d2731ac256a4a88c1094dfa74
```

IPA checksum относится к локальной упаковке; повторная ZIP упаковка может изменить hash из-за timestamps, не меняя содержимое. Библиотека выше взята из указанного успешного CI; её iOS sources совпадают с текущими исходниками (последующие изменения — Python packaging/tests/docs).

## Производительность на синтетике

`python -m scripts.benchmark --frames 120`, Windows11, движущаяся правая рука из собственного кинематического шаблона, независимый Gaussian pixel noise σ=0.6 px:

| Метрика | Результат |
|---|---:|
| Кадров / отклонено | 120 / 0 |
| Средний solve | 16.92 ms/hand |
| P95 solve | 17.36 ms/hand |
| Mean reprojection error | 0.77 px |
| Mean depth error against synthetic model | 7.46 mm |

Cold-start smoke solve: 66.89 ms. Отдельный stationary warm-start замер ранее давал около 7 ms/hand. Реальные руки отличаются от шаблона; 7.46 mm **не является оценкой точности реального монокулярного tracking**. Две руки, Vision, сеть и rendering требуют дополнительного времени. Целевые 60 FPS и end-to-end latency на iPhone не подтверждены.

## Аппаратные блокировки и ограничения

* Нет подключённого доступного iPhone: не проверены camera format/FPS, Vision output на устройстве, notifications, simultaneous capture/VRidge streaming, LAN discovery именно iPhone↔PC, thermal behaviour и установка IPA.
* Подходящие certificate/private key/profile/entitlements не предоставлены: подписанная IPA и установка stock iOS не заявляются.
* XInput poll вернул disconnected: реальный Xbox input/hot-unplug в SteamVR не проверены; mapping/neutral release и независимый поток проверены автоматически.
* OpenVR вернул `InitError_Init_NoServerForBackgroundApp`: реальные left/right Index devices, pose updates и игровые bindings в текущей сессии не проверены.
* Lens distortion calibration и camera-to-HMD mount не измерены. Нулевой mount/grip offset и шаблон ладони — исходные параметры, а не аппаратно подтверждённая калибровка.
* Монокулярная глубина/roll/back-facing неоднозначны. Local covariance и 15% depth floor не являются эмпирически подтверждённым confidence interval. Полностью перекрывающиеся руки могут сменить identity.
* GlassVR UDP имеет только curl+splay skeleton и не имеет tracked/valid flag; потерянная рука freezes, кнопки освобождаются. Это ограничение выбранного upstream API.
* Нет результатов длительного hardware soak test, ground-truth orientation accuracy или display latency. Наличие passing tests не заменяет эти проверки.

Проект пока **не отвечает всем аппаратным критериям готовности**. Код, локальные build artifacts и процедура проверки предоставлены; полный приёмочный список находится в [README](../README.md#аппаратная-приёмка).
