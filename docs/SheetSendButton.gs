/**
 * Скрипт для кнопки «Отправить сообщение» в Google Таблице (Номера).
 *
 * Установка:
 * 1. Откройте таблицу → Расширения → Apps Script.
 * 2. Удалите весь код в редакторе и вставьте этот файл целиком.
 * 3. Сохраните (Ctrl+S).
 * 4. Обновите таблицу (F5) — в меню появится «Номера».
 *
 * Чтобы в каждой строке был «переключатель» отправки:
 *   Номера → Добавить флажки «Отправить» во все строки
 * После этого в колонке H в каждой строке будет флажок. Отметьте нужные и запустите: python send_sheet_messages.py
 */

// Колонка «Отправить» (H = 8)
var COL_SEND = 8;

/**
 * При открытии таблицы добавляет меню «Номера».
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Номера')
    .addItem('Добавить флажки «Отправить» во все строки', 'addSendCheckboxes')
    .addSeparator()
    .addItem('Отправить по этой строке', 'markRowToSend')
    .addItem('Отправить по выбранным строкам', 'markSelectedRowsToSend')
    .addToUi();
}

/**
 * Добавляет флажки (чекбоксы) в колонку H «Отправить» для всех строк с данными (со 2-й до последней заполненной в колонке A).
 * Запустите один раз — в каждой строке появится флажок. Отметьте нужные строки и выполните на компьютере: python send_sheet_messages.py
 */
function addSendCheckboxes() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert('В таблице нет данных (нужна хотя бы одна строка под заголовком).');
    return;
  }
  var range = sheet.getRange(2, COL_SEND, lastRow, COL_SEND);
  var rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  range.setDataValidation(rule);
  SpreadsheetApp.getActiveSpreadsheet().toast('Флажки добавлены в колонку «Отправить» (строки 2–' + lastRow + '). Отметьте нужные и запустите: python send_sheet_messages.py');
}

/**
 * Ставит «1» в колонке H для строки, в которой находится активная ячейка.
 * Вызывается из кнопки или меню «Номера» → «Отправить по этой строке».
 */
function markRowToSend() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var row = sheet.getActiveCell().getRow();
  if (row <= 1) {
    SpreadsheetApp.getUi().alert('Выберите ячейку в строке с данными (не в заголовке).');
    return;
  }
  sheet.getRange(row, COL_SEND).setValue('1');
  SpreadsheetApp.getActiveSpreadsheet().toast('В строке ' + row + ' отмечено «Отправить». Запустите: python send_sheet_messages.py');
}

/**
 * Ставит «1» в колонке H для всех строк в текущем выделении.
 * Меню «Номера» → «Отправить по выбранным строкам».
 */
function markSelectedRowsToSend() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var range = sheet.getActiveRange();
  if (!range) {
    SpreadsheetApp.getUi().alert('Выделите диапазон строк.');
    return;
  }
  var startRow = range.getRow();
  var numRows = range.getNumRows();
  if (startRow <= 1) {
    SpreadsheetApp.getUi().alert('Выделение не должно включать заголовок (строка 1).');
    return;
  }
  var colH = sheet.getRange(startRow, COL_SEND, startRow + numRows - 1, COL_SEND);
  colH.setValue('1');
  SpreadsheetApp.getActiveSpreadsheet().toast('В ' + numRows + ' строках отмечено «Отправить». Запустите: python send_sheet_messages.py');
}
