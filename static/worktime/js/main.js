function main() {

  var currentModeElem = document.getElementById('current-mode');
  var currentElapsedElem = document.getElementById('current-elapsed');
  var totalsElem = document.getElementById('totals-table');
  var statsElem = document.getElementById('stats');
  var historyElem = document.getElementById('history');
  var historyTimespanElem = document.getElementById('history-timespan');
  var historyBarElem = document.getElementById('history-bar');
  var connectionElem = document.getElementById('connection-status');

  var lastUpdate = Date.now()/1000;
  connectionElem.textContent = "Current";
  flashGreen(connectionElem);

  function applySummary() {
    // Insert the new data into the page.
    // Called once the XMLHttpRequest has gotten a response.
    var summary = this.response;
    if (summary) {
      applyStatus(summary, currentModeElem, currentElapsedElem);
      applyTotals(summary, totalsElem);
      applyHistory(summary, historyTimespanElem, historyBarElem);
      lastUpdate = Date.now()/1000;
    }
  }

  function updateConnection() {
    var now = Date.now()/1000;
    var age = now - lastUpdate;
    /* Set the age text. */
    var humanAge = humanTime(age);
    var content = humanAge+" ago";
    if (age < 60) {
      connectionElem.style.color = "initial";
    } else {
      content += "!";
      connectionElem.style.color = "red";
    }
    connectionElem.textContent = content;
    if (age <= 1) {
      flashGreen(connectionElem);
    }
    /* Fade out the status info as it gets out of date. */
    var opacity = getOpacity(age);
    statsElem.style.opacity = opacity;
    historyElem.style.opacity = opacity;
    //TODO: Could add a bar to the history display representing the unknown period since the last
    //      update. Color it something weird like purple.
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
  window.setInterval(updateConnection, 1*1000);
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
    if (period.mode === null) {
      var mode = 'None';
    } else {
      var mode = period.mode;
    }
    var periodElem = document.createElement('span');
    periodElem.classList.add('period');
    periodElem.classList.add('mode-'+mode);
    periodElem.style.width = period.width+"%";
    periodElem.setAttribute('title', mode+" "+period.timespan);
    historyBarElem.appendChild(periodElem);
  }
}

function removeChildren(element) {
  while (element.childNodes.length > 0) {
    element.removeChild(element.childNodes[0]);
  }
}

function getOpacity(seconds) {
  /* This is tuned so that anything under 1 minute gives an opacity of 1, and it decreases from
   * there, at a slower rate as the time increases. The minimum it ever returns is 0.1, which
   * occurs around 1 hour 45 minutes. Examples:
   * 5 minutes:  0.62
   * 15 minutes: 0.41
   * 1 hour:     0.19
   */
  var rawOpacity = 11.0021/Math.log(seconds*1000);
  var transparency = 3 * (1 - rawOpacity);
  var opacity = 1 - transparency;
  var opacityRounded = Math.round(opacity*100)/100;
  return Math.max(0.1, Math.min(1, opacityRounded));
}

function flashGreen(element, delay) {
  /* Highlight an element with a green background that quickly fades out. */
  if (delay === undefined) {
    delay = 50;
  }
  var startTime = Date.now() + delay;
  function updateGreen() {
    var age = Date.now() - startTime;
    var bgOpacity = Math.max((3000-age)/3000, 0);
    element.style.backgroundColor = "rgba(200, 255, 200, "+bgOpacity+")";
    if (bgOpacity > 0) {
      window.setTimeout(updateGreen, 50);
    }
  }
  window.setTimeout(updateGreen, delay);
}

function humanTime(seconds) {
  seconds = Math.round(seconds);
  if (seconds < 60) {
    return formatTime(seconds, 'second');
  } else if (seconds < 60*60) {
    return formatTime(seconds/60, 'minute');
  } else if (seconds < 24*60*60) {
    return formatTime(seconds/60/60, 'hour');
  } else if (seconds < 10*24*60*60) {
    return formatTime(seconds/60/60/24, 'day');
  } else if (seconds < 40*24*60*60) {
    return formatTime(seconds/60/60/24/7, 'week');
  } else if (seconds < 365*24*60*60) {
    return formatTime(seconds/60/60/24/30.5, 'month');
  } else {
    return formatTime(seconds/60/60/24/365, 'year');
  }
}

function formatTime(quantity, unit) {
  if (quantity < 10) {
    // Round to 1 decimal place if less than 10.
    var rounded = Math.round(quantity*10)/10;
  } else {
    // Round to a whole number if more than 10.
    var rounded = Math.round(quantity);
  }
  var output = rounded + ' ' + unit;
  if (rounded !== 1) {
    output += 's';
  }
  return output;
}

window.addEventListener('load', main, false);
