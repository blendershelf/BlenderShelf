# EasyShelf: проверка на правила extensions.blender.org

Проверено 2026-10-04 по первоисточникам: [Terms of Service](https://extensions.blender.org/terms-of-service/) (редакция 10.08.2026) и страницы Blender Manual: getting_started, addons, licenses, tags. Сборка: `python build_extension.py --edition easyshelf` → `dist\easy_shelf-0.3.0.zip`.

## Итог по правилам

| Правило | Статус | Что сделано / что осталось |
|---|---|---|
| ToS 2.1 «Blender» не в названии | ОК | Название и id: EasyShelf / `easy_shelf`. Сборка падает, если в имени есть «blender». |
| ToS 2.2 нет логотипа Blender в иконке/превью | Проверить | В zip картинок логотипа нет. Иконку и превью для страницы расширения нужно сделать новые (старый «B»-логотип BlenderShelf не подходит по имени) и убедиться, что на скриншотах нет логотипа Blender. |
| ToS 2.3 нет ложной аффилиации | ОК | В описании не писать «official/for Blender by Blender». «for Blender» допустимо. |
| ToS 1.1 / licenses: аддон GPL-3.0-or-later | ОК | В манифесте `SPDX:GPL-3.0-or-later`, файл LICENSE в zip. |
| **ToS 1.2 / licenses: ресурсы (картинки) только CC0** | **НЕ РЕШЕНО** | В `icons/` лежат 700 PNG, производные от иконок Blender (673 + 14 + 13). Иконки Blender распространяются под GPL, не CC0 ([обсуждение лицензии](https://devtalk.blender.org/t/license-for-blender-icons/5522)). Это главный риск отказа. Варианты ниже. |
| ToS 3.1 «без сюрпризов», описание полное | Нужно описание | Черновик ниже. Обязательно указать, что кнопки и «Add Script» исполняют Python-код пользователя. |
| ToS 3.5 нет обфускации | ОК | Код читаемый. |
| ToS 3.6 только Python, без бинарников | ОК | В zip нет .dll/.so/.pyd/.exe/.pyc. |
| **ToS 3.9 не вмешиваться во внутренности Blender и чужие расширения** | **Исправлено** | Легаси-версия патчила `execute` встроенного экспортёра FBX (`io_scene_fbx`). В сборке EasyShelf этот код вырезан. Побочный эффект: у кнопки «Export FBX» на шелфе экспорт идёт по выделению, актуальному на момент подтверждения в диалоге, а не на момент клика. |
| ToS 5.3 нет зависимостей от других расширений | Исправлено | Импорт `io_scene_fbx` тоже вырезан. |
| ToS 4.x интернет | Исправлено | Проверка обновлений удалена вместе с кодом `urllib`. Разрешение `network` в манифесте убрано. |
| ToS 6.3 не рекламировать обновления в UI Blender | Исправлено | Кнопка «Check for Updates» и надпись «Update available» вырезаны (обновления идут через платформу). |
| ToS 6.1 нет донат-ссылок в UI | ОК | Ссылок на Boosty/DonationAlerts в коде нет (проверено поиском). Ссылки на донаты можно давать только в описании на платформе. |
| Manual: `permissions.files` для файловых операций | Добавлено | `files = "Export and import settings and scripts"` (39 символов, без точки). |
| Manual: tagline ≤64 символов без знака в конце | ОК | 55 символов. |
| Manual: теги из списка | ОК | `3D View`, `User Interface` есть в списке. |
| Manual: `bl_info` убрать | Сделано | В сборке EasyShelf `bl_info` удалён. |
| Manual: данные пользователя не в папке аддона | ОК | Конфиг пишется в `extension_path_user`. |
| Manual: manifest валиден | ОК | `blender --command extension validate` (Blender 5.2.2) прошёл. |

## Что проверено на практике (Blender 5.2.2, фоновый режим, изолированная копия)
- zip проходит `extension validate`;
- устанавливается и включается без ошибок, отключается чисто;
- в EasyShelf нет оператора обновления и патча FBX;
- перенос настроек работает: старый `shelf_config.json` из BlenderShelf (расширение или папка `scripts/addons/BlenderShelf`) копируется при первом запуске, поле `top_margin=77` дошло до настроек. Старая копия остаётся нетронутой;
- существующий тест `tests/check_contexts.py` проходит на изменённом исходнике;
- легаси-сборка `blender_shelf-0.3.0.zip` собирается как раньше.

**Не проверено:** отрисовка шелфа в окне Blender с графическим интерфейсом (фоновый режим окон не создаёт). Перед загрузкой установите zip через «Install from Disk» в обычном Blender 4.2 и в 5.x и пройдитесь по основным функциям.

## Открытые вопросы
1. **Иконки (ToS 1.2).** Варианты:
   - спросить у команды платформы до подачи (devtalk или форма), допускают ли иконки Blender как ресурсы, раз они тоже GPL и идут с самим Blender;
   - заменить набор на CC0-иконки (потребуется перерисовка или подбор набора с лицензией CC0; для остальных лицензий требуется указать авторов в манифесте);
   - не поставлять PNG, а брать иконки из установленного Blender во время работы (большая переделка, оверлей рисуется своими текстурами).
   Рекомендую сначала спросить у платформы, это ничего не стоит.
2. **Прошлая заявка BlenderShelf в Extensions.** Если она ещё в очереди модерации, её надо отозвать. Если её уже отклонили, посмотрите причины: они подскажут, на что смотрят модераторы.
3. **Формат страницы расширения** (размеры иконки и превью, описание): в документации этого нет, смотреть на странице загрузки `/submit/` после входа через Blender ID.
4. **Исполнение пользовательского кода.** Кнопки шелфа и «Add Script / Import Script» запускают Python, который вводит сам пользователь (не из сети). Правила прямо не запрещают, но модератор может задать вопрос. Поэтому это явно указано в описании.
5. **Сайт и ссылки.** В манифесте `website` указывает на сайт BlenderShelf. Пока сайт не переведён, пусть так. После ребрендинга обновить версию расширения.

## Черновик описания для страницы расширения (English)

> **EasyShelf** puts a floating, draggable shelf of one-click buttons in the 3D Viewport, UV Editor and Node Editor, plus an optional radial pie menu on a hotkey.
>
> - Right-click any button in Blender's interface (including buttons from other add-ons) and choose "Add to Shelf".
> - Each shelf button can run a Blender operator or a short Python script. Scripts are typed or imported by you ("Add Script" / "Import Script"); EasyShelf never downloads or runs code from the internet.
> - Settings can be exported to and imported from a JSON file.
> - If you used BlenderShelf, your shelf is copied over on first launch.
>
> The add-on does not connect to the internet. It needs file access only for exporting and importing settings and scripts through Blender's file browser.
>
> EasyShelf is free and open source (GPL-3.0-or-later). It is not affiliated with or endorsed by the Blender Foundation.
>
> Support the project: <ссылка на Boosty/DonationAlerts — разрешено только в описании на платформе>
