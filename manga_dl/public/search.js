let previousQuery = "";
let searched_querys = [];
let queryResults = {};

const timePassed = (d1, d2) => {
  let diff = Math.abs(d1 - d2) / 1000;
  return diff;
};

// on search send post request to /search with query

let searchTime = new Date();
$("#search").on("keyup", function () {
  let query = $(this).val();
  if (query.length < 3) {
    return;
  }

  // wait for 500ms before sending request
  setTimeout(() => {
    let now = new Date();
    if (timePassed(searchTime, now) >= 0.5) {
      searchTime = now;
      searchQuery($(this).val());
    }
  }, 500);
});

function searchQuery(query) {
  if (query.length < 3) {
    return;
  }

  if (queryResults[query]) {
    add_results(queryResults[query]);
    return;
  }

  const search = $("#search");
  if (search.val() != query) {
    search.val(query);
  }

  // replace / with %%% to avoid url encoding
  const encodedQuery = encodeURIComponent(query.replace("/", "%%%"));
  window.history.pushState("", "", "/search/" + encodedQuery);
  document.title = "Search: " + query;

  $("#spinner").removeClass("d-none");
  $.ajax({
    url: "/api/search",
    type: "POST",
    contentType: "application/json",
    data: JSON.stringify({ query: query }),
    dataType: "json",
    success: function (data) {
      // add to queryResults
      if (Object.keys(queryResults).length > 20) {
        delete queryResults[Object.keys(queryResults)[0]];
      }
      queryResults[query] = data;
      add_results(data);
    },
  });
}

// add results to the page
function add_results(data) {
  $("#spinner").addClass("d-none");
  const results = data.results;
  if (results.length == 0) {
    $("#results").html("<h3>No results found</h3>");
  } else {
    $("#results").html("");

    for (let i = 0; i < results.length; i++) {
      let result = results[i];

      let last_chapter = result.last_chapter;
      if (last_chapter.length > 15) {
        last_chapter = last_chapter.substring(0, 15) + "...";
      }

      let last_part = `<span class="dots"></span><small>${last_chapter}</small><span class="dots"></span>`;
      if (!last_chapter) {
        last_part = "";
      }

      let cover_url = result.cover_url;
      if (!cover_url) {
        cover_url = "/public/error.png";
      }

      let html = `<div class="mt-3 manga" id="m-${result.id}">
              <div class="d-flex justify-content-between align-items-center">
                <div class="d-flex flex-row align-items-center">
                <div class="d-flex flex-column showimg" style="padding-right: 10px;">
                  <img src="${cover_url}" class="rounded" style="width: 70px; height: 100px;" />
                </div>
                  <div class="d-flex flex-column">
                    <span>${result.title}</span>
                    <div class="d-flex flex-row align-items-center time-text">
                      <small>${result.author}</small>
                     ${last_part}
                    <small>${result.domain}</small>
                    </div>
                  </div>
                </div>
              </div>
            </div>`;
      $("#results").append(html);
    }
  }
}

$(document).on("click", ".manga", function () {
  let id = $(this).attr("id").replace("m-", "");
  window.location.href = "/manga/" + id;
});
