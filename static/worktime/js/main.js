function main() {

  var currentModeElem = document.getElementById('currentMode');
  var currentElapsedElem = document.getElementById('currentElapsed');
  var totalsElem = document.getElementById('totalsTable');

  function applySummary() {
    // Insert the new data into the page.
    // Called once the XMLHttpRequest has gotten a response.
    var summary = this.response;
    applyStatus(summary, currentModeElem, currentElapsedElem);
    applyTotals(summary, totalsElem);
  }

  function updateSummary() {
    makeRequest('GET', applySummary, '/worktime?format=json&numbers=text&via=js');
  }

  window.setInterval(updateSummary, 60*1000);
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
    //TODO: Create element if it doesn't exist.
    currentElapsedElem.textContent = summary.current_elapsed;
  } else {
    //TODO: Delete element if it exists.
  }
}

function applyTotals(summary, totalsElem) {
  removeChildren(totalsElem);
  for (var i = 0; i < summary.elapsed.length; i++) {
    var total = summary.elapsed[i];
    var row = makeRow(total.mode, total.time);
    totalsElem.appendChild(row);
  }
  if (summary.ratio_str) {
    var row = makeRow(summary.ratio_str, summary.ratio);
    totalsElem.appendChild(row);
  }
}

function makeRow(name, value) {
  var row = document.createElement('tr');
  var nameCell = document.createElement('td');
  var valueCell = document.createElement('td');
  nameCell.className = 'name';
  valueCell.className = 'value';
  nameCell.textContent = name;
  valueCell.textContent = value;
  row.appendChild(nameCell);
  row.appendChild(valueCell);
  return row;
}

function removeChildren(element) {
  while (element.children.length > 0) {
    element.removeChild(element.children[0]);
  }
}

window.addEventListener('load', main);
