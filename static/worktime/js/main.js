function main() {

  var modeTimeElem = document.getElementById('mode-time');
  var currentModeElem = document.getElementById('current-mode');
  var currentElapsedElem = document.getElementById('current-elapsed');
  var totalsElem = document.getElementById('totals-table');
  var statsElem = document.getElementById('stats');
  var historyElem = document.getElementById('history');
  var historyTimespanElem = document.getElementById('history-timespan');
  var historyBarElem = document.getElementById('history-bar');
  var connectionElem = document.getElementById('connection-status');
  var connectionWarningElem = document.getElementById('connection-warning');
  var adjustmentsBarElem = document.getElementById('adjustments-bar');
  var adjustmentLinesBarElem = document.getElementById('adjustment-lines-bar');

  var lastUpdate = Date.now()/1000;
  connectionElem.textContent = "Current";
  flashGreen(connectionElem);

  function applySummary() {
    // Insert the new data into the page.
    // Called once the XMLHttpRequest has gotten a response.
    var summary = this.response;
    if (summary && summary.elapsed && summary.history) {
      unwarn(connectionWarningElem);
      updateStatus(summary, modeTimeElem, currentModeElem, currentElapsedElem);
      updateTotals(summary, totalsElem);
      updateHistory(summary, historyTimespanElem, historyBarElem);
      updateAdjustments(summary, adjustmentsBarElem, adjustmentLinesBarElem);
      lastUpdate = Date.now()/1000;
      //TODO: Somehow, the lastUpdate is getting set to now even when the request fails.
      //      Is `if (summary)` not properly detecting the failure?
    } else if (summary) {
      warn(connectionWarningElem, "Invalid summary object returned");
    } else {
      warn(connectionWarningElem, "No summary object returned");
    }
  }

  function connectionWarn(event) {
    warn(connectionWarningElem, "Could not connect to server");
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
      makeRequest('GET', applySummary, '/worktime?format=json&numbers=text&via=js', connectionWarn);
    }
  }

  function visibilityHandler() {
    updateSummary();
  }

  addPopupListeners(historyBarElem);
  arrangeAdjustments(adjustmentsBarElem);
  window.setInterval(updateSummary, 30*1000);
  window.setInterval(updateConnection, 1*1000);
  document.addEventListener('visibilitychange', visibilityHandler, false);
}

function makeRequest(method, callback, url, errorCallback) {
  var request = new XMLHttpRequest();
  request.responseType = 'json';
  request.addEventListener('load', callback, true);
  if (errorCallback) {
    request.addEventListener('error', errorCallback, true);
  }
  request.open(method, url);
  request.send();
}


/***** UPDATE DISPLAYED DATA *****/

function updateStatus(summary, modeTimeElem, currentModeElem, currentElapsedElem) {
  modeTimeElem.className = "mode-"+summary.current_mode;
  currentModeElem.textContent = summary.current_mode;
  if (summary.current_mode) {
    currentElapsedElem.textContent = summary.current_elapsed;
  } else {
    currentElapsedElem.textContent = "";
  }
}

function updateTotals(summary, totalsElem) {
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

function updateHistory(summary, historyTimespanElem, historyBarElem) {
  if (!summary.history) {
    return;
  }
  historyTimespanElem.textContent = "Past "+summary.history.timespan+":";
  /* Create the bar display. */
  removeChildren(historyBarElem);
  // Make the popups.
  for (var i = 0; i < summary.history.periods.length; i++) {
    var period = summary.history.periods[i];
    if (period.mode === null) {
      var mode = 'None';
    } else {
      var mode = period.mode;
    }
    var popupElem = document.createElement('div');
    popupElem.classList.add('popup');
    popupElem.textContent = mode+" "+period.timespan;
    popupElem.dataset.index = i;
    historyBarElem.appendChild(popupElem);
  }
  // Make the period bars.
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
    periodElem.dataset.index = i;
    periodElem.setAttribute('title', mode+" "+period.timespan);
    periodElem.addEventListener('click', showPopup, false);
    historyBarElem.appendChild(periodElem);
  }
}

function updateAdjustments(summary, adjustmentsBarElem, adjustmentLinesBarElem) {
  removeChildren(adjustmentsBarElem);
  removeChildren(adjustmentLinesBarElem);
  for (var i = 0; i < summary.history.adjustments.length; i++) {
    var adjustment = summary.history.adjustments[i];
    if (adjustment.mode === null) {
      var mode = 'None';
    } else {
      var mode = adjustment.mode;
    }
    // Make the display box.
    var adjustmentElem = document.createElement('span');
    adjustmentElem.classList.add('adjustment');
    adjustmentElem.classList.add('mode-'+mode);
    adjustmentElem.style.left = adjustment.x+"%";
    adjustmentElem.textContent = mode+" "+adjustment.sign+adjustment.magnitude;
    adjustmentsBarElem.appendChild(adjustmentElem);
    // Make the indicator line.
    var adjustmentLineElem = document.createElement('span');
    adjustmentLineElem.classList.add('adjustment-line');
    adjustmentLineElem.style.left = adjustment.x+"%";
    adjustmentLinesBarElem.appendChild(adjustmentLineElem);
  }
  arrangeAdjustments(adjustmentsBarElem);
}

function removeChildren(element) {
  while (element.childNodes.length > 0) {
    element.removeChild(element.childNodes[0]);
  }
}


/********** POPUPS **********/

// This section is to show a popup with the length of the period when the user clicks on a period.
// It's mainly for mobile, where the normal alt text doesn't show.

function addPopupListeners(historyBarElem) {
  for (var i = 0; i < historyBarElem.children.length; i++) {
    var child = historyBarElem.children[i];
    if (child.classList.contains("period")) {
      child.addEventListener("click", showPopup);
    }
  }
}

function showPopup(event) {
  var index = event.target.dataset.index;
  var historyBarElem = event.target.parentElement;
  var popupElem = null;
  for (var i = 0; i < historyBarElem.children.length; i++) {
    var child = historyBarElem.children[i];
    if (child.classList.contains("popup") && child.dataset.index === index) {
      popupElem = child;
    }
  }
  if (popupElem === null) {
    console.log("Error: Could not locate the correct popupElem.");
    return;
  }
  popupElem.style.left = (event.clientX+window.scrollX-25)+"px";
  popupElem.style.top = (event.clientY+window.scrollY-10)+"px";
  popupElem.style.opacity = 1;
  popupElem.style.display = "inline-block";
  fadeOut(popupElem, 5);
}

function fadeOut(element, timespan) {
  var start = Date.now()/1000;
  element.dataset.fadeStart = start;
  function updateFade() {
    if (element.dataset.fadeStart !== ""+start) {
      return;
    }
    var now = Date.now()/1000;
    var elapsed = now-start;
    if (elapsed >= timespan) {
      element.style.opacity = 1;
      element.style.display = "none";
    } else {
      element.style.opacity = 1 - elapsed/timespan;
      window.setTimeout(updateFade, 50);
    }
  }
  updateFade();
}


/***** FRESHNESS INDICATORS *****/

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


/***** MISC *****/

function warn(warningElem, warning) {
  console.log(warning);
  warningElem.textContent = warning;
  warningElem.style.display = "initial";
}

function unwarn(warningElem) {
  warningElem.textContent = "";
  warningElem.style.display = "none";
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
