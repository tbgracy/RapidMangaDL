function getNumber(str, asc = false) {
  let m = str.match(/\d+/);
  if (m) {
    return parseInt(m[0]);
  } else {
    return asc ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
  }
}

function getViews(views) {
  if (views.includes("K")) {
    views = views.slice(0, -1);
    views = parseFloat(views) * 1000;
  } else if (views.includes("M")) {
    views = views.slice(0, -1);
    views = parseFloat(views) * 1000000;
  } else {
    views = parseFloat(views);
  }
  return views;
}

function getTime(str) {
  let time = null;
  if (str.includes("ago")) {
    // change a year ago or a day ago, etc to 1 year ago or 1 day ago
    const replacers = {
      "a year ago": "1 year ago",
      "a day ago": "1 day ago",
      "an hour ago": "1 hour ago",
      "a minute ago": "1 minute ago",
      "a second ago": "1 second ago",
      "just now": "1 second ago",
    };

    for (const [key, value] of Object.entries(replacers)) {
      // convert to lower case
      const lowerStr = str.toLowerCase();
      if (lowerStr.includes(key)) {
        str = str.replace(key, value);
        break;
      }
    }

    const ago = parseInt(str, 10);
    if (!isNaN(ago)) {
      // if days,hours,minutes,seconds ago
      const currentDate = new Date();
      if (str.includes("year")) {
        currentDate.setFullYear(currentDate.getFullYear() - ago);
      } else if (str.includes("days")) {
        currentDate.setDate(currentDate.getDate() - ago);
      } else if (str.includes("hours")) {
        currentDate.setHours(currentDate.getHours() - ago);
      } else if (str.includes("min")) {
        currentDate.setMinutes(currentDate.getMinutes() - ago);
      } else if (str.includes("sec")) {
        currentDate.setSeconds(currentDate.getSeconds() - ago);
      }
      time = currentDate.getTime();
    }
  } else if (str.includes("Today")) {
    const hoursAgo = parseInt(relativeTime, 10);
    if (!isNaN(hoursAgo)) {
      const currentDate = new Date();
      currentDate.setHours(currentDate.getHours() - hoursAgo);
      time = currentDate.getTime();
    }
  } else if (str.includes("Yesterday")) {
    const hoursAgo = parseInt(relativeTime, 10);
    if (!isNaN(hoursAgo)) {
      const currentDate = new Date();
      currentDate.setHours(currentDate.getHours() - hoursAgo);
      time = currentDate.getTime();
    }
  } else {
    const date = new Date(str);
    time = date.getTime();
  }

  return isNaN(time) ? 0 : time;
}

// if click on the image show the modal
$("#slider-items").on("click", ".carousel-item", function () {
  // get the image src
  const src = $(this).find("img").attr("src");
  // set the image src to the modal
  $("#imagepreview").attr("src", src);
  // show the modal
  $("#imagemodal").modal("show");
});

const sortDesc = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-sort-down" viewBox="0 0 16 16">
              <path d="M3.5 2.5a.5.5 0 0 0-1 0v8.793l-1.146-1.147a.5.5 0 0 0-.708.708l2 1.999.007.007a.497.497 0 0 0 .7-.006l2-2a.5.5 0 0 0-.707-.708L3.5 11.293V2.5zm3.5 1a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5zM7.5 6a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm0 3a.5.5 0 0 0 0 1h3a.5.5 0 0 0 0-1h-3zm0 3a.5.5 0 0 0 0 1h1a.5.5 0 0 0 0-1h-1z"/>
              </svg>`;
const sortAsc = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-sort-up-alt" viewBox="0 0 16 16">
      <path d="M3.5 13.5a.5.5 0 0 1-1 0V4.707L1.354 5.854a.5.5 0 1 1-.708-.708l2-1.999.007-.007a.498.498 0 0 1 .7.006l2 2a.5.5 0 1 1-.707.708L3.5 4.707V13.5zm4-9.5a.5.5 0 0 1 0-1h1a.5.5 0 0 1 0 1h-1zm0 3a.5.5 0 0 1 0-1h3a.5.5 0 0 1 0 1h-3zm0 3a.5.5 0 0 1 0-1h5a.5.5 0 0 1 0 1h-5zM7 12.5a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 0-1h-7a.5.5 0 0 0-.5.5z"/>
    </svg>`;

$("#sort").on("click", function () {
  const isDesc = $(this).hasClass("desc");
  if (isDesc) {
    $(this).removeClass("desc");
    $(this).html(sortAsc);

    // sort by data-time="Jun 23,23" and if data-time is equal sort by number on the chapter[1]="Chapter 1", "Extra. 200"
    $("#chapters > a")
      .sort(function (a, b) {
        const aTime = getTime($(a).data("time"));
        const bTime = getTime($(b).data("time"));
        if (aTime == bTime) {
          const aNumber = getNumber($(a).text(), true);
          const bNumber = getNumber($(b).text(), true);
          return aNumber - bNumber;
        } else {
          return aTime - bTime;
        }
      })
      .appendTo("#chapters");
  } else {
    $(this).addClass("desc");
    $(this).html(sortDesc);

    $("#chapters > a")
      .sort(function (a, b) {
        const aTime = getTime($(a).data("time"));
        const bTime = getTime($(b).data("time"));
        if (aTime == bTime) {
          const aNumber = getNumber($(a).text());
          const bNumber = getNumber($(b).text());
          return bNumber - aNumber;
        } else {
          return bTime - aTime;
        }
      })
      .appendTo("#chapters");
  }
});

$("#downloadBtn").on("click", function () {
  // show downloadModal
  $("#downloadModal").modal("show");
});

function changeDownloadButtonProgress(value) {
  const dlbtn = $(".two-color-element");
  const whitePercentage = 100 - value;
  dlbtn.css(
    "background",
    `linear-gradient(to right, var(--bs-primary) ${value}%, var(--bs-body-color) ${whitePercentage}%)`
  );
}

let interval = null;
function changeProgress(value, progress) {
  // if value not in range 0-100 return
  if (value < 0 || value > 100 || Number.isNaN(value)) return;
  changeDownloadButtonProgress(parseInt(value));

  value = `${value}%`;
  $("#progress").css("width", value);
  $("#progress").text(progress.desc);
  $("#progress-value").text(value);
  if (value == "100%") {
    $("#downloadBtn").find("span").text("Download");
  } else {
    $("#downloadBtn")
      .find("span")
      .text(`${progress.desc} ${value} ${progress.current}/${progress.total}`);
  }

  console.log("Changing progress", value);
}

function updateProgress() {
  $.ajax({
    url: "/api/manga/download/progress",
    type: "GET",
    success: function (data) {
      if (data.success) {
        const progress = data.progress;
        const isDownloading = data.isDownloading;
        if (isDownloading) {
          changeProgress(
            Math.floor((progress.current / progress.total) * 100),
            progress
          );
        } else {
          changeProgress(100, progress);
          clearInterval(interval);
        }
      }
    },
    error: function (xhr, status, error) {
      console.log(xhr);
      console.log(status);
      console.log(error);
      if (interval) {
        changeProgress(100, { desc: "Error", current: 0, total: 0 });
        clearInterval(interval);
      }
    },
  });
}

let downloading = false;
$("#downBtn").on("click", function () {
  // get chapter-start, chapter-end select value
  const chapterStart = $("#chapter-start").val();
  const chapterEnd = $("#chapter-end").val();

  // .downType all checked value
  const downType = $(".downType");
  const types = [];
  for (let i = 0; i < downType.length; i++) {
    if (downType[i].checked) {
      types.push(downType[i].value);
    }
  }

  // .dquality value
  const dquality = $("#dquality").val();
  if (downloading) {
    console.log("downloading");
    return;
  }
  downloading = true;
  console.log(chapterStart, chapterEnd, dquality, types);
  interval = setInterval(updateProgress, 2000);
  $.ajax({
    url: "/api/manga/download",
    type: "POST",
    data: JSON.stringify({
      start_id: chapterStart,
      end_id: chapterEnd,
      quality: dquality,
      dtypes: types,
      manga_id: mangaID,
    }),
    contentType: "application/json",
    success: function (data) {
      let msg = "";
      if (!data.success) {
        msg = `<div class="text-center">${data.message}</div>`;
      } else {
        const paths = data.paths;
        let message = "";
        for (let i = 0; i < paths.length; i++) {
          message += `<p class="text-center">${paths[i]}</p>`;
        }
        msg = message;
      }

      $("#downloadedModal").find(".modal-body").html(msg);
      $("#downloadedModal").modal("show");

      downloading = false;
    },
    error: function (xhr, status, error) {
      console.log(xhr);
      console.log(status);
      console.log(error);
      downloading = false;
    },
  });
});

$("#dquality").on("input", function () {
  $("#dquality-label").text(`Quality ${$(this).val()}`);
});
