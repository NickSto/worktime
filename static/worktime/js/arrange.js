
function arrangeAdjustments(adjustmentsBarElem) {
  var totalWidth = adjustmentsBarElem.offsetWidth;
  var adjustments = gatherAdjustmentsData(adjustmentsBarElem, totalWidth);
  // Center the boxes over their time points.
  // console.log("Centering boxes..");
  for (var i = 0; i < adjustments.length; i++) {
    var adjustment = adjustments[i];
    adjustment.currentLeft = adjustment.idealPosition - (adjustment.width/2);
    // logGeometry(adjustment);
  }
  // Make sure nothing goes past the edge of the bar.
  // console.log("Keeping boxes inside the bar..");
  for (var i = 0; i < adjustments.length; i++) {
    var adjustment = adjustments[i];
    if (adjustment.currentLeft + adjustment.width > totalWidth) {
      adjustment.currentLeft = totalWidth - adjustment.width;
    } else if (adjustment.currentLeft < 0) {
      adjustment.currentLeft = 0;
    }
    // logGeometry(adjustment);
  }
  // Space the boxes out to remove overlaps.
  // console.log("Removing overlaps..");
  var tries = 0;
  var overlapping = true;
  while (overlapping && tries < 10) {
    // This uses a naive and simple algorithm that just keeps looping over the adjustments, spacing
    // out any that overlap, until none do.
    // console.log("Try #"+tries);
    var overlapRuns = getOverlapRuns(adjustments);
    if (overlapRuns.length > 0) {
      overlapping = true;
      shiftOverlapRuns(overlapRuns, totalWidth);
    } else {
      // console.log("No overlaps found!");
      overlapping = false;
    }
    tries++;
    if (tries >= 10) {
      console.log("Warning: Could not remove overlaps in adjustments bar.");
    }
  }
  // console.log("Applying changes..");
  for (var i = 0; i < adjustments.length; i++) {
    var adjustment = adjustments[i];
    var leftPct = Math.round(10 * 100 * adjustment.currentLeft / totalWidth) / 10;
    adjustment.elem.style.left = leftPct + "%";
  }
}

// Gather geometry data. All dimensions are stored in pixels.
function gatherAdjustmentsData(adjustmentsBarElem, totalWidth) {
  var adjustments = [];
  for (var i = 0; i < adjustmentsBarElem.children.length; i++) {
    var adjustmentElem = adjustmentsBarElem.children[i];
    var idealPosition = totalWidth * parseFloat(adjustmentElem.style.left) / 100;
    adjustments[i] = {elem:adjustmentElem, idealPosition:idealPosition, currentLeft:idealPosition,
                  width:getNaturalWidth(adjustmentElem)};
    // logGeometry(adjustments[i]);
  }
  return adjustments;
}

// Kludge to get the width of the element without text wrapping.
function getNaturalWidth(adjustmentElem) {
  // We temporarily move the element to the center to make sure there's no wrapping, measure its
  // width, then set it back.adjustment
  var oldLeft = adjustmentElem.style.left;
  adjustmentElem.style.left = "50%";
  var width = adjustmentElem.offsetWidth;
  adjustmentElem.style.left = oldLeft;
  return width;
}

// Group runs of adjustments that overlap.
function getOverlapRuns(adjustments) {
  var overlapRuns = [];
  var currentRun = [];
  var doneAdjustments = {};
  for (var i = 0; i < adjustments.length-1; i++) {
    var firstRight = adjustments[i].currentLeft + adjustments[i].width;
    var secondLeft = adjustments[i+1].currentLeft;
    if (firstRight >= secondLeft) {
      // Overlap. Add both to the current run.
      if (! doneAdjustments[i]) {
        currentRun.push(adjustments[i]);
        doneAdjustments[i] = true;
      }
      if (! doneAdjustments[i+1]) {
        currentRun.push(adjustments[i+1]);
        doneAdjustments[i+1] = true;
      }
    } else {
      // No overlap. Finish the current run and start a new one.
      if (currentRun.length > 0) {
        overlapRuns.push(currentRun);
      }
      currentRun = [];
    }
  }
  if (currentRun.length > 0) {
    overlapRuns.push(currentRun);
  }
  return overlapRuns;
}

function shiftOverlapRuns(overlapRuns, totalWidth) {
  /*TODO: Detect when one end of a run is up against the edge of the bar, and compensate.
   *      There are several scenarios where this can happen:
   *      1. A common one is when displaying an adjustment that was just made. It will be squished
   *         up against the right side, and it'll be wrapped. It may not even overlap with the one
   *         to its left, so just detecting this situation is an issue.
   */
  var MIN_SPACE = 5; // minimum pixels between adjustments.
  for (var i = 0; i < overlapRuns.length; i++) {
    // console.log("Overlap run "+i+":");
    var overlapRun = overlapRuns[i];
    if (overlapRun.length < 2) {
      // console.log("Error: overlapRun.length === "+overlapRun.length);
      return;
    } else if (overlapRun.length === 2) {
      // The run is just two adjustments that overlap.
      var leftAdjustment = overlapRun[0];
      var rightAdjustment = overlapRun[1];
      // console.log("Shifting "+leftAdjustment.elem.textContent.trim()+" from "+
      //             leftAdjustment.currentLeft);
      // console.log("     and "+rightAdjustment.elem.textContent.trim()+" from "+
      //             rightAdjustment.currentLeft);
      var overlapWidth = getOverlapWidth(leftAdjustment, rightAdjustment);
      var shiftAmount = (overlapWidth + MIN_SPACE)/2;
      // console.log("  Found overlap of "+overlapWidth+". Shifting by "+shiftAmount+".");
      leftAdjustment.currentLeft -= shiftAmount;
      rightAdjustment.currentLeft += shiftAmount;
    } else {
      // A run of 3 or more adjustments. Just shift the outermost two.
      var leftAdjustment = overlapRun[0];
      var rightAdjustment = overlapRun[overlapRun.length-1];
      // console.log("Shifting "+leftAdjustment.elem.textContent.trim()+" from "+
      //             leftAdjustment.currentLeft);
      // console.log("     and "+rightAdjustment.elem.textContent.trim()+" from "+
      //             rightAdjustment.currentLeft);
      var overlapWidth = getOverlapWidth(leftAdjustment, overlapRun[1]);
      // console.log("  Found first overlap: "+overlapWidth+". Shifting "+
      //             leftAdjustment.elem.textContent.trim()+" by "+(-(overlapWidth + MIN_SPACE))+".");
      leftAdjustment.currentLeft -= overlapWidth + MIN_SPACE;
      var overlapWidth = getOverlapWidth(overlapRun[overlapRun.length-2], rightAdjustment);
      // console.log("  Found first overlap: "+overlapWidth+". Shifting "+
      //             rightAdjustment.elem.textContent.trim()+" by "+(overlapWidth + MIN_SPACE)+".");
      rightAdjustment.currentLeft += overlapWidth + MIN_SPACE;
    }
    if (leftAdjustment.currentLeft < 0) {
      // console.log(leftAdjustment.elem.textContent.trim()+" was over the left border. "+
      //             "Resetting to 0.");
      leftAdjustment.currentLeft = 0;
    }
    if (rightAdjustment.currentLeft + rightAdjustment.width > totalWidth) {
      // console.log(rightAdjustment.elem.textContent.trim()+" was over the right border. "+
      //             "Resetting to "+(totalWidth-rightAdjustment.width)+".");
      rightAdjustment.currentLeft = totalWidth - rightAdjustment.width;
    }
    // for (var j = 0; j < overlapRun.length; j++) {
    //   logGeometry(overlapRun[j]);
    // }
  }
}

function getOverlapWidth(leftAdjustment, rightAdjustment) {
  var firstRight = leftAdjustment.currentLeft + leftAdjustment.width;
  var secondLeft = rightAdjustment.currentLeft;
  return firstRight - secondLeft;
}

function logGeometry(adjustment) {
  console.log(adjustment.elem.textContent.trim()+": ideal: "+adjustment.idealPosition+", current: "+
              adjustment.currentLeft+", width: "+adjustment.width);
}
