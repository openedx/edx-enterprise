(function($){
    $(document).ready(function(){
        var catalogQueryId,
            // Django admin does auto form filling once the form is loaded.
            // We want to ignore the first two "on change event on enterprise_catalog_query dropdown".
            // The reason to ignore this is for the case when we might have manually updated the
            // content_filter field and when loading the admin page, Django populates the form, fills the
            // dropdown field, which will trigger an "on change event on enterprise_catalog_query dropdown".
            numTriggeredUpdates = 0,
            catalogQueryApiUrl = '/enterprise/api/v1/enterprise_catalog_query/',
            $contentFilterEl = $('#id_content_filter');

        $("[name='enterprise_catalog_query']").on("change", function(event){
            catalogQueryId = $(event.target).val();
            if (numTriggeredUpdates > 1 && catalogQueryId) {
                // Extract content_filter for the selected catalogQueryId.
                $.ajax({
                    url: catalogQueryApiUrl + catalogQueryId + '/',
                    method: "get"
                }).done(function (catalogQueryResponse) {
                    $contentFilterEl.val(JSON.stringify(catalogQueryResponse));
                });
            }
            // Turn on the logic to extract content_filter.
            numTriggeredUpdates += 1;
        }).change();
    });
})(jQuery);