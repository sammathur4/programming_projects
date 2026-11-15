// Google Apps Script: format the UPSC question bank sheet.
// Usage: Extensions -> Apps Script -> paste -> select formatSheet -> Run.
// Authorizes on first run.

function formatSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  // Target the sheet with gid 2002042591 if present, else active sheet.
  let sheet = null;
  ss.getSheets().forEach(s => { if (s.getSheetId() === 2002042591) sheet = s; });
  if (!sheet) sheet = ss.getActiveSheet();

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return;

  const header = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const idx = {};
  header.forEach((h, i) => idx[String(h).trim()] = i + 1); // 1-based col

  // --- base styling ---
  sheet.setFrozenRows(1);
  if (idx.id) sheet.setFrozenColumns(idx.id);
  const headerRange = sheet.getRange(1, 1, 1, lastCol);
  headerRange.setFontWeight('bold')
    .setBackground('#1f3864').setFontColor('#ffffff')
    .setHorizontalAlignment('center').setVerticalAlignment('middle')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  sheet.setRowHeight(1, 30);

  // auto filter
  if (sheet.getFilter()) sheet.getFilter().remove();
  sheet.getRange(1, 1, lastRow, lastCol).createFilter();

  // column widths
  const widths = {
    id: 60, question_id: 70, year: 60, paper: 110, section: 130,
    question: 420, option_a: 260, option_b: 260, option_c: 260, option_d: 260,
    correct_answer: 70, explanation: 420, motivation: 260, difficulty: 90,
    nature: 120, source: 120, source_type: 120, source_file: 160,
    created_at: 150, updated_at: 150, tags: 160, relevance: 80,
    current_affairs_linkage: 260, is_repeated_theme: 160,
    option_a_explanation: 200, option_b_explanation: 200,
    option_c_explanation: 200, option_d_explanation: 200,
    why_correct: 300, marks: 60, negative_marks: 80
  };
  Object.keys(widths).forEach(name => {
    if (idx[name]) sheet.setColumnWidth(idx[name], widths[name]);
  });

  // wrap text for long text columns
  ['question','option_a','option_b','option_c','option_d','explanation',
   'motivation','current_affairs_linkage','why_correct',
   'option_a_explanation','option_b_explanation','option_c_explanation','option_d_explanation','tags']
    .forEach(name => { if (idx[name]) sheet.getRange(2, idx[name], lastRow-1, 1).setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP); });

  // number formats
  if (idx.marks) sheet.getRange(2, idx.marks, lastRow-1, 1).setNumberFormat('0.00');
  if (idx.negative_marks) sheet.getRange(2, idx.negative_marks, lastRow-1, 1).setNumberFormat('0.0000');
  ['created_at','updated_at'].forEach(name => {
    if (idx[name]) sheet.getRange(2, idx[name], lastRow-1, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  });

  // center small columns
  ['id','question_id','year','correct_answer','difficulty','relevance','marks','negative_marks']
    .forEach(name => { if (idx[name]) sheet.getRange(2, idx[name], lastRow-1, 1).setHorizontalAlignment('center'); });

  // data validation dropdowns
  const dv = (col, values) => {
    if (!idx[col]) return;
    const rule = SpreadsheetApp.newDataValidation()
      .requireValueInList(values, true).setAllowInvalid(false).build();
    sheet.getRange(2, idx[col], lastRow-1, 1).setDataValidation(rule);
  };
  dv('year', ['2013','2014','2015','2016','2017','2018','2019','2020','2021','2022','2023','2024','2025','2026']);
  dv('paper', ['Prelims GS','Prelims CSAT']);
  dv('difficulty', ['Easy','Medium','Difficult']);
  dv('correct_answer', ['a','b','c','d']);
  dv('relevance', ['High','Medium','Low']);
  dv('source_type', ['Previous Year Question','Testbook','EM','EN','RM','RR','RF']);

  // conditional formatting: difficulty colors
  const rules = [];
  const diffRange = idx.difficulty ? sheet.getRange(2, idx.difficulty, lastRow-1, 1) : null;
  if (diffRange) {
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Easy').setBackground('#d9ead3').setRanges([diffRange]).build());
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Medium').setBackground('#fff2cc').setRanges([diffRange]).build());
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Difficult').setBackground('#f4cccc').setRanges([diffRange]).build());
  }
  // highlight empty required cells
  ['question','option_a','option_b','option_c','option_d','correct_answer','explanation']
    .forEach(name => {
      if (!idx[name]) return;
      const r = sheet.getRange(2, idx[name], lastRow-1, 1);
      rules.push(SpreadsheetApp.newConditionalFormatRule()
        .whenCellEmpty().setBackground('#fce4ec').setRanges([r]).build());
    });
  sheet.setConditionalFormatRules(rules);

  // hide fully-empty columns
  for (let c = 1; c <= lastCol; c++) {
    const colVals = sheet.getRange(2, c, lastRow-1, 1).getValues();
    if (colVals.every(v => String(v[0]).trim() === '')) sheet.hideColumns(c);
  }

  SpreadsheetApp.getUi().alert('Formatted: ' + sheet.getName());
}

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Format')
    .addItem('Format this sheet', 'formatSheet')
    .addToUi();
}
