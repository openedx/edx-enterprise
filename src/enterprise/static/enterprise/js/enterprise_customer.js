(function($){
    $(document).ready(function(){
        var $catalog_anchor = $("#catalog-details-link"),
            // URL template with a place holder '{catalog_id}'
            // Sample url template: http://localhost:18381/admin/catalogs/catalog/{catalog_id}/change/
            url_template = $catalog_anchor.data("urlTemplate"),
            selected_catalog = 0;

        $("[name='catalog']").on("change", function(event){
            selected_catalog = $(event.target).val();
            $catalog_anchor.attr(
                "href", selected_catalog && url_template.replace("{catalog_id}", selected_catalog)
            ).text(
                selected_catalog && "View catalog '{catalog_name}' details.".replace(
                    "{catalog_name}", $(event.target).find("option:selected").text()
                )
            );
        }).change();
    });
})(django.jQuery);
