/*TODO: New system that's more like a physics model of forces acting on objects.
 *      It'll be divided into [X] phases:
 *      1. Resolve overlaps.
 *         Like I'm doing now, I'll first detect runs (blocks) of overlapping boxes.
 *         Then I'll find the midpoint of each block. If it's an even number of boxes, just pick
 *         either one of the middle two (doesn't matter much). And if the block overlaps one of the
 *         edges, just call the edge the midpoint. The midpoint will be represented as an index in
 *         the array holding the boxes in the block. If the midpoint is the edge, pick a midpoint of
 *         -1 for the left edge, or the number of boxes for the right edge.
 *         Then, I'll move through the block, shifting each box by its overlap distance. I'll move
 *         it left if its i is < the midpoint, and right if its i is > the midpoint. If there are
 *         blocks of more than 2 boxes, it'll take multiple passes to do this. Ideally, at the end,
 *         boxes that were overlapping will be directly adjacent to each other (touching).
 *         NOTE: I might need a sort step after each of these iterations to make sure the array is
 *         still in the same order that the boxes are now laid out.
 *         Actually, maybe I should just write something that'll shift a whole set of boxes by a
 *         given amount. Then start at the center of the block and work outward, one box at a time.
 *      2. Calculate restorative (anchor) forces.
 *         Once the overlaps are resolved (or it runs out of tries), I'll go through all the boxes
 *         and calculate how far each one is from its ideal position (anchor). I'll translate these
 *         distances into forces acting to push the boxes toward their anchors.
 *      3. Group into blocks of co-moving boxes.
 *         Again I'll find runs of boxes that are touching (or overlap, if that wasn't fixed). But
 *         this time, I'll take into account the anchor forces. Boxes will only be grouped into the
 *         same block if they're both touching and their anchor forces are pushing them together.
 *         If two touching boxes have forces in opposite directions, they'll be in different blocks.
 *         Also, if one's force is toward the other, but the other's isn't, they'll only count as
 *         the same block if the force pushing them together is greater than the one pushing them
 *         apart.
 *      4. Calculate the force on each block.
 *         Once I have contiguous blocks, I'll sum up the anchor forces for each box in the block,
 *         then divide by the number of boxes, and that'll be the force on the block.
 *      5. Move the blocks.
 *         Then, I guess I'll move each block by a number of pixels equal to (or proportional to?)
 *         the force on it. And I can do some math checking how far each block is from the edge to
 *         make sure it doesn't go past it. Maybe I can do the same for neighboring blocks, to keep
 *         them from overlapping.
 *      6. Rinse and repeat.
 *         Then, I can repeat steps 2-5 until it reaches some sort of steady state.
 */

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
