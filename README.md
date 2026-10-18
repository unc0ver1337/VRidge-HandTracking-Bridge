# VRidge MobRecon Experimental — iPhone client

Полностью отдельная экспериментальная IPA. Основной [VRidge Hand Tracking Bridge](https://github.com/unc0ver1337/VRidge-HandTracking-Bridge) и релиз 2.5.1 не меняются.

**3D-кисть рассчитывает настоящий MobRecon DenseStack + SpiralConv** из [HandMesh, Xingyu Chen и соавторы](https://github.com/SeanChenxy/HandMesh), commit `3c87e958d4855f890e3884ec94bcfc0f99422c3d`, официальный checkpoint `mobrecon_densestack.pt`. Core ML-модель содержит обученный backbone, mesh decoder и регрессию 21 сустава. Это не переименование MediaPipe.

## Как работает

```text
iPhone ultra-wide camera 640x480 / 30 FPS capture
  -> Apple Vision: 2D ROI + left/right side (up to two hands)
  -> upright crop; left hand mirrored into right-hand model convention
  -> MobRecon Core ML: 778 mesh vertices -> 21 wrist-relative 3D joints + 2D joints
  -> undo crop rotation/mirror; estimate camera translation; palm quaternion
  -> existing MPBR/v2 UDP -> unchanged Windows 2.5.1 -> GlassVR -> SteamVR
```

Vision здесь нужен только для обнаружения/выбора участка и стороны руки. Координаты 3D, включая скрытые суставы, вычисляет MobRecon. В IPA нет моделей MediaPipe и нет подмены 3D фиксированной глубиной. Без валидного MobRecon результата поза не отправляется как достоверная.

## Установка

1. Скачать тестовую IPA из Releases этого приватного репозитория. Она unsigned — подписать своим совместимым способом.
2. Название: **VRidge MobRecon Test**, bundle ID `com.riftcat.vridge2.mobrecon.experimental`. Это отдельное приложение; основной VRidge сохраняется. URL schemes основного приложения не перехватываются.
3. Разрешить камеру и локальную сеть, настроить обычный VRidge stream в тестовом приложении при необходимости.
4. Использовать существующий Windows bridge **2.5.1**. ПК-билд менять не требуется: размеры, порядок суставов, quaternion и сетевой протокол сохранены. Запускать только один iPhone-клиент и один bridge одновременно.
5. Проверить обе руки, ладонь/тыльную сторону/ребро, исчезновение и возвращение, затем захват с Joy-Con. Сохранить bridge.log и сообщить реальные FPS/нагрев.

Кнопочные жесты не добавлены. Фиксированный хват ПК 2.5.1 не изменён; новая модель может давать отличающуюся оценку ориентации.

## Точность, скорость и проверки

Модель экспортируется в **FP32**: пробный FP16 экспорт не прошёл установленный допуск сравнения с PyTorch. Это осознанный выбор для первого теста; скорость и фактическое использование Neural Engine на iPhone ещё не измерены. Разрешены CPU + ANE, GPU оставлен VRidge. Захват 30 FPS не гарантирует 30 inference FPS при двух руках.

CI проверяет строгую загрузку официальных весов по SHA256, эквивалентность sparse pooling и dense matmul, PyTorch/Core ML parity на трёх реальных изображениях и зеркальных копиях. Дополнительно: native ROI/crop/mirroring tests, 980 synthetic translation poses, Python protocol/packaging tests, native Vision+MobRecon smoke на macOS CPU_ONLY. Это не проверка реального iPhone и не доказательство превосходства над MediaPipe.

Монокулярная глубина остаётся оценкой. Vision может терять ROI при перекрытии, MobRecon может ошибаться на непривычных ракурсах и объектах в руках. Для ROI применяется 1.3x crop, как в upstream training, но bounds получены из Vision joints вместо silhouette. Повороты и mirror преобразуются одинаково для 2D и 3D; масштаб модели 0.20 взят из upstream demo.

## Сборка

macOS + Xcode + Python 3.11:

```sh
python -m pip install torch==2.7.1 coremltools==9.0 numpy==1.26.4 scipy==1.15.3 opencv-python-headless==4.11.0.86 gdown==5.2.0
bash ios/build.sh
python tests/native_mobrecon_smoke.py
```

На Windows сборка модели/Core ML runtime недоступна; используйте macOS CI. `ios/build` содержит dylib, mobrecon.mlmodelc и отчёты. Для обновления уже инжектированной IPA: `python -m scripts.update_injected_ipa --ipa private/input.ipa --dylib ios/build/VRidgeHandTracking.dylib --output artifacts/VRidge-MobRecon-Unsigned.ipa`. Обновление сохраняет основной executable, удаляет старые модели/подписи и включает MobRecon. IPA/сертификаты не попадают в git или CI.

## Авторы

- **Xingyu Chen и соавторы — MobRecon / HandMesh**: обученная модель и mesh pipeline, MIT source notice в third_party/MobRecon-LICENSE.txt.
- **DaniXmir — GlassVR**: существующая эмуляция OpenVR/Index и skeleton; ПК-драйвер не переписывается.
- Интеграция VRidge/iPhone/Windows — unc0ver1337. VRidge принадлежит RiftCat.

См. THIRD_PARTY.md: лицензия нашего кода не перелицензирует модели, MANO-производные шаблоны или проприетарное приложение.
