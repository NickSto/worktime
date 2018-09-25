function main() {

  var currentModeElem = document.getElementById('currentMode');
  var currentElapsedElem = document.getElementById('currentElapsed');
  var totalsElem = document.getElementById('totalsTable');
  var historyTimespanElem = document.getElementById('history-timespan');
  var historyBarElem = document.getElementById('history-bar');

  function applySummary() {
    // Insert the new data into the page.
    // Called once the XMLHttpRequest has gotten a response.
    var summary = this.response;
    if (summary) {
      applyStatus(summary, currentModeElem, currentElapsedElem);
      applyTotals(summary, totalsElem);
      applyHistory(summary, historyTimespanElem, historyBarElem);
    }
  }

  function updateSummary() {
    // Only update when the tab is visible.
    // Note: This isn't supported in IE < 10, so if you want to support that, you should check:
    // https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
    if (!document.hidden) {
      makeRequest('GET', applySummary, '/worktime?format=json&numbers=text&via=js');
    }
  }

  function visibilityHandler() {
    updateSummary();
  }

  window.setInterval(updateSummary, 30*1000);
  document.addEventListener('visibilitychange', visibilityHandler, false);
}

function makeRequest(method, callback, url) {
  var request = new XMLHttpRequest();
  request.responseType = 'json';
  request.addEventListener('load', callback, true);
  request.open(method, url);
  request.send();
}

function applyStatus(summary, currentModeElem, currentElapsedElem) {
  currentModeElem.textContent = summary.current_mode;
  if (summary.current_mode) {
    currentElapsedElem.textContent = summary.current_elapsed;
  } else {
    currentElapsedElem.textContent = "";
  }
}

function applyTotals(summary, totalsElem) {
  removeChildren(totalsElem);
  for (var i = 0; i < summary.elapsed.length; i++) {
    var total = summary.elapsed[i];
    var row = makeRow("", total.mode, total.time);
    totalsElem.appendChild(row);
  }
  for (var i = 0; i < summary.ratios.length; i++) {
    var ratio = summary.ratios[i];
    if (i === 0) {
      var rowspan = summary.ratios.length;
      var name1 = summary.ratio_str;
    } else {
      var rowspan = null;
      var name1 = null;
    }
    var row = makeRow(name1, ratio['timespan'], ratio['value'], rowspan);
    totalsElem.appendChild(row);
  }
}

function makeRow(name1, name2, value, rowspan) {
  var row = document.createElement('tr');
  if (name1 !== null) {
    var name1Cell = document.createElement('td');
    name1Cell.className = 'name';
    if (name1 === "") {
      name1Cell.classList.add('dummy');
    }
    name1Cell.textContent = name1;
    if (rowspan) {
      name1Cell.setAttribute('rowspan', rowspan);
    }
    row.appendChild(name1Cell);
  }
  var name2Cell = document.createElement('td');
  var valueCell = document.createElement('td');
  name2Cell.className = 'name';
  valueCell.className = 'value';
  name2Cell.textContent = name2;
  valueCell.textContent = value;
  row.appendChild(name2Cell);
  row.appendChild(valueCell);
  return row;
}

function applyHistory(summary, historyTimespanElem, historyBarElem) {
  if (!summary.history) {
    return;
  }
  historyTimespanElem.textContent = "Past "+summary.history.timespan+":";
  /* Create the bar display. */
  removeChildren(historyBarElem);
  for (var i = 0; i < summary.history.periods.length; i++) {
    var period = summary.history.periods[i];
    var periodElem = document.createElement('span');
    periodElem.classList.add('period');
    periodElem.classList.add('mode-'+period.mode);
    periodElem.style.width = period.width+"%";
    periodElem.setAttribute('title', period.mode+" "+period.timespan);
    historyBarElem.appendChild(periodElem);
  }
}

function removeChildren(element) {
  while (element.childNodes.length > 0) {
    element.removeChild(element.childNodes[0]);
  }
}

window.addEventListener('load', main, false);
