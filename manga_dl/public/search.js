let previousQuery = "";
let searched_querys = [];
let queryResults = {};

const timePassed = (d1, d2) => {
  let diff = Math.abs(d1 - d2) / 1000;
  return diff;
};


// on search send post request to /search with query

$("#search").on("keyup", function () {
  let query = $(this).val().trim();
  if (query.length < 3) {
    return;
  }
  searched_querys.push(query);
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

  const encodedQuery = encodeURIComponent(query);
  window.history.pushState("", "", "/search/" + encodedQuery);
  document.title = "Search: " + query;
  

  $("#spinner").removeClass("d-none");
  $.ajax({
    url: "/search",
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

const searchInterval = setInterval(() => {
  if (searched_querys.length > 0) {
    let query = searched_querys[searched_querys.length - 1];
    searched_querys = [];
    searchQuery(query);
  }
}, 1000);

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
      let html = `<div class="mt-3 manga" id="m-${result.id}">
              <div class="d-flex justify-content-between align-items-center">
                <div class="d-flex flex-row align-items-center">
                <div class="d-flex flex-column showimg" style="padding-right: 10px;">
                  <img src="${result.cover_url}" class="rounded" style="width: 70px; height: 100px;" />
                </div>
                  <div class="d-flex flex-column">
                    <span>${result.title}</span>
                    <div class="d-flex flex-row align-items-center time-text">
                      <small>${result.author}</small>
                      <span class="dots"></span>
                      <small>${result.last_chapter}</small>
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
  let id = $(this).attr("id").split("-")[1];
  window.location.href = "/manga/" + id;
});
