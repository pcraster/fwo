/*
    JavaScript for providing the functionality on the feedback page in a user's
    workspace. Everything is stored in the FWO.comments.* variable.
*/
var FWO=$.extend(FWO || {},{
    feedback:{
        /*
        FWO.feedback.*

        Code and variables for leaving feedback at a certain point.
        */
        map:undefined,
        show:function(coord) {
            /*
            FWO.feedback.show(coord)

            Show the feedback modal centered on the location specified in coord. We clone
            the main map and add a map marker in the center where the original click event
            registered.
            */

            /*
            We can only show a feedback modal if a DOM element is present for the model.
            */
            if(! document.getElementById("feedback-modal")){
                return false;
            } else {
                /* 
                Show the bootstrap modal dialog 
                */
                $('#feedback-modal').modal('show');

                /* 
                Empty the comments field 
                */
                $('#comment_body').val("")

                /* 
                Fetch a bunch of properties from the original map. We will apply these to the
                mini feedback map which is present in the modal dialog.
                */
                var view = new ol.View({ center: coord, zoom: FWO.map.obj.getView().getZoom() })

                /*
                Create a vector source, icon style, and vector layer which show the map marker
                in the position defined in coords variable.
                */
                var vectorSource = new ol.source.Vector({'features':[new ol.Feature({geometry:new ol.geom.Point(coord)})]});
                var iconStyle = new ol.style.Style({image: new ol.style.Icon( ({anchor: [0.5, 48],anchorXUnits: 'fraction', anchorYUnits: 'pixels',opacity: 1,src: '/static/gfx/m2.png'}))});
                var vectorLayer = new ol.layer.Vector({source: vectorSource,style: iconStyle});

                /*
                We don't want to recreate the small map in the modal dialog every time the
                comments link is clicked, so only initialize the "feedback-map" instance once,
                namely when FWO.feedback.map is undefined. All the next times the map will
                exist already and we can just update it to set the correct extent, view, etc.
                */
                if(FWO.feedback.map == undefined) {
                    FWO.feedback.map = new ol.Map({target: 'feedback-map'});
                }

                /*
                Update the feedback map with the properties (view, extent, etc) from the large
                map.
                */
                FWO.feedback.map.setView(view) //Set the same view as the main map.
                FWO.map.obj.getLayers().forEach(function(lyr,ix,ar){ FWO.feedback.map.addLayer(lyr) }) //Add the same layers to the feedback map as the main map.
                FWO.feedback.map.addLayer(vectorLayer) //Add the vector layer with the map marker

                /*
                Update the "map_state", "map_center", "map_view", and "map_marker" input fields. In
                addition to the comment, these are all required to be able to recreate the same 
                map on the "Comments and Feedback" page.
                */
                var view = FWO.feedback.map.getView()
                $('form#feedback-form input[name="map_marker"]').val(coord[0]+","+coord[1])
                $('form#feedback-form input[name="map_state"]').val(FWO.map.getvisiblelayers().join("|"))
                $('form#feedback-form input[name="map_center"]').val(view.getCenter())
                $('form#feedback-form input[name="map_view"]').val(view.getCenter()+","+view.getZoom())


                /*
                And trigger that call as well when there is a mapmove event on the small feedback map.
                */
                FWO.feedback.map.on('moveend',function(){
                    var view = FWO.feedback.map.getView()
                    $('form#feedback-form input[name="map_center"]').val(view.getCenter())
                    $('form#feedback-form input[name="map_view"]').val(view.getCenter()+","+view.getZoom())
                })
            }

        },
        submit:function(evt) {
            /*
            FWO.feedback.submit()

            Submits the feedback form. The submit button is disabled while the form is 
            submitted to prevent double-clicking from submitting the form twice.
            */
            evt.preventDefault()
            $('button#feedback-modal-submit').prop("disabled",true)
            $.ajax({
                type:"POST",
                url: $(this).attr('action'),
                data: $(this).serialize(),
                success: function(data){
                    $('button#feedback-modal-submit').prop("disabled",false)
                    $('#feedback-modal').modal('hide');
                },
                error: function() {
                    alert("An error occurred while trying to post your comment!")
                    $('button#feedback-modal-submit').prop("disabled",false)
                }
            })
        }
    }
})
