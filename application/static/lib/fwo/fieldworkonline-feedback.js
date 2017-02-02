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
	init:function() {
		if(FWO.feedback.map == undefined) {
                    FWO.feedback.map = new L.Map('feedback-map', {
			    'zoomControl': false,
			    'dragging': false,
		    });
                }
		
		FWO.feedback.vectorLayer = new L.layerGroup()
		
	},
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
                Create a vector source, icon style, and vector layer which show the map marker
                in the position defined in coords variable.
                */
		var icon = new L.Icon({iconUrl: '/static/gfx/m2.png', iconAnchor: [24, 48]});
		var vector = new L.Marker(coord, {icon: icon});
		FWO.feedback.vectorLayer.clearLayers()
		FWO.feedback.vectorLayer.addLayer(vector)

                /*
                Update the feedback map with the properties (view, extent, etc) from the large
                map.
                */
                FWO.feedback.map.fitBounds(FWO.map.obj.getBounds()) //Set the same view as the main map.
		//FWO.feedback.map.addLayer(FWO.map.BackgroundLayer)
		//FWO.feedback.map.addLayer(FWO.map.VisibleLayers)
                FWO.feedback.map.addLayer(FWO.feedback.vectorLayer) //Add the vector layer with the map marker

                /*
                Update the "map_state", "map_center", "map_view", and "map_marker" input fields. In
                addition to the comment, these are all required to be able to recreate the same 
                map on the "Comments and Feedback" page.
                */
                $('form#feedback-form input[name="map_marker"]').val(coord.lat+","+coord.lng)
                $('form#feedback-form input[name="map_state"]').val(FWO.map.getvisiblelayers().join("|"))
                $('form#feedback-form input[name="map_center"]').val(FWO.feedback.map.getCenter().lat+","+FWO.feedback.map.getCenter().lng)
                $('form#feedback-form input[name="map_view"]').val(FWO.feedback.map.getCenter().lat+","+FWO.feedback.map.getCenter().lng+","+FWO.feedback.map.getZoom())


                /*
                And trigger that call as well when there is a mapmove event on the small feedback map.
                */
                FWO.feedback.map.on('moveend',function(){
                    $('form#feedback-form input[name="map_center"]').val(FWO.feedback.map.getCenter().lat+","+FWO.feedback.map.getCenter().lng)
                    $('form#feedback-form input[name="map_view"]').val(FWO.feedback.map.getCenter().lat+","+FWO.feedback.map.getCenter().lng+","+FWO.feedback.map.getZoom())
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
