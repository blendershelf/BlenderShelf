# Сайт EasyShelf: что сделано и что осталось

Владелец на GitHub: **`easyshelf-addon`** (на 2026-10-04 имя свободно, организацию создаёт владелец в браузере).
Адрес сайта: `https://easyshelf-addon.github.io/EasyShelf/`. Репозиторий: `easyshelf-addon/EasyShelf` (здесь же Pages и релизы).

Сборка: `python easyshelf/build_site.py --owner easyshelf-addon` → `easyshelf\site\`.
Манифест расширения уже указывает на этот адрес (`website`).

## Шаги запуска
1. Создать организацию `easyshelf-addon` (github.com/account/organizations/new, бесплатный тариф).
2. Создать репозиторий `EasyShelf`, залить в корень Pages содержимое `easyshelf\site\` (Pages: ветка main, корень или /docs), включить Pages.
3. Релиз `v0.3.0` с файлом **`EasyShelf.zip`** (это `easyshelf\dist\easy_shelf-0.3.0.zip`, переименованный). Имя стабильное: `releases/latest/download/EasyShelf.zip`.
4. Задеплоить обновлённый Worker (разрешает запросы с нового сайта): `cd worker; npx wrangler deploy` (запускает владелец сам в PowerShell).
5. Новый счётчик GoatCounter (`easyshelf`) и вставить его скрипт в `index.html`; в копии он убран.

## Форма обратной связи
Форма на новом сайте работает через **старый Worker** (`blendershelf-feedback.denis-ghome.workers.dev`), отзывы попадают в старый репозиторий `blendershelf/BlenderShelf`. В тексте issue добавляется строка `_Site: easyshelf-addon.github.io_`, чтобы отличать сайты. Адрес Worker остаётся в `feedback.js` (виден только в исходном коде страницы).
Пока Worker не задеплоен, форма на новом сайте будет получать ошибку CORS.

## Убрано из копии (показывали старое имя)
- Видеогайд (YouTube) и PDF-инструкции RU/EN.

## Остаётся с прежним именем
- **Скриншоты** `assets\screenshots\*`: на `pie-menu.png` в центре меню подпись «BlenderShelf». Переснять с EasyShelf, остальные просмотреть.
