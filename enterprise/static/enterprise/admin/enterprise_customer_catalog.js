(function($){
    $(document).ready(function(){
        var catalogQueryId,
            ignoreUpdate = true,
            catalogQueryApiUrl = '/enterprise/api/v1/enterprise_catalog_query/',
            $contentFilterEl = $('#id_content_filter');

        $("[name='enterprise_catalog_query']").on("change", function(event){
            catalogQueryId = $(event.target).val();
            if (!ignoreUpdate && catalogQueryId) {
                // for some reasons $.cookie is not defined in this scope.
                function readCookie(name) {
                    var nameEQ = name + "=";
                    var ca = document.cookie.split(';');
                    for(var i=0;i < ca.length;i++) {
                        var c = ca[i];
                        while (c.charAt(0)==' ') c = c.substring(1,c.length);
                        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
                    }
                    return null;
                };

                // Fetch catalogQuery for the selected catalogQueryId.
                $.ajax({
                    url: catalogQueryApiUrl + catalogQueryId,
                    method: "get",
                    beforeSend: function (xhr) {
                        // $.cookie("csrftoken")
                        xhr.setRequestHeader("X-CSRFToken", readCookie('csrftoken'));
                    }
                }).success(function (catalogQueryResponse) {
                    $contentFilterEl.val(JSON.stringify(catalogQueryResponse.content_filter));
                });
            }
            ignoreUpdate = false;
        }).change();
    });
})(django.jQuery);
