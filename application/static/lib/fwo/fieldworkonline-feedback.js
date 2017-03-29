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
		init:function() {
			FWO.feedback.vectorLayer = new L.layerGroup()
			FWO.feedback.popup = new L.popup({
				offset:[110,-20],
				minWidth:400,
				minHeight:400,
				closeButton:false,
			})

			popupcontent = $("<div />", {
				"style": "background-color:transparent;",
				"id":"feedback-popup"
			})

			form = $("<form />", {
				"id":"feedback-form",
				"action":"feedback"
			})

			body = $("<div />", {
				"style":"margin-top:5px;padding-bottom:0;background-color:white;"
			})
			.append($("<small>Add Georeference feedback or comments. This map view will be shown alongside your comments or feedback.</small>"))
			.append($("<div />", {
				"class":"form-group",
				"style":"padding-top:5px; margin-bottom:0;"
			}).append('<textarea name="comment_body" class="form-control" id="comment_body" placeholder=""></textarea>'))

			footer = $("<div />", {
				"style":"border-top:none;padding-top:2px;background-color:white;"
			})

			footer.append('<button type="button" class="btn btn-default" id="feedback-close">Close</button>')
			footer.append('<button type="submit" class="btn btn-primary" id="feedback-modal-submit"><i class="fa fa-comment"></i> Submit</button>')
			footer.append('<input type="hidden" name="map_state" placeholder="map_state" />')
			footer.append('<input type="hidden" name="map_view" placeholder="map_view" />')
			footer.append('<input type="hidden" name="map_marker" placeholder="map_marker" />')

			form.append(body, footer)

			form.submit(function() {
				$('button#feedback-modal-submit').prop("disabled",true)
				$.post($(this).attr('action'), $(this).serialize(), function(response){
				}, 'json')
				.success(function() {
					alert("Your feedback has been submitted")
					FWO.feedback.vectorLayer.clearLayers()
				});
				return false;
			});
			form.on('click', 'button#feedback-close', function() {
				FWO.feedback.vectorLayer.clearLayers()
			})
			popupcontent.append(form)

			FWO.feedback.popup.setContent(popupcontent[0])

		},
		show:function(coord) {
			/*
            	FWO.feedback.show(coord)

                Show the bootstrap modal dialog

		    	TO DO: Convert feedback modal HTML to popup, which opens on link click. Transparent element in the middle
		    	with the marker icon showing as anchor. Submission of feedback should be similar.
            	*/
			/*
                Empty the comments field
                */

			/*
                Create a vector source, icon style, and vector layer which show the map marker
                in the position defined in coords variable.
                */
			var icon = new L.Icon({iconUrl: '/static/gfx/m2.png', iconAnchor: [24, 48]});
			var vector = new L.Marker(coord, {icon: icon});
			FWO.feedback.vectorLayer.clearLayers()
			vector.bindPopup(FWO.feedback.popup)
			FWO.feedback.vectorLayer.addLayer(vector)
			vector.openPopup()
			$('#comment_body').val("")
			/*
                Update the feedback map with the properties (view, extent, etc) from the large
                map.
                */
			FWO.map.obj.addLayer(FWO.feedback.vectorLayer) //Add the vector layer with the map marker

			/*
                Update the "map_state", "map_center", "map_view", and "map_marker" input fields. In
                addition to the comment, these are all required to be able to recreate the same
                map on the "Comments and Feedback" page.
                */
			center = FWO.map.obj.getCenter()
			$('form#feedback-form input[name="map_marker"]').val(coord.lat+","+coord.lng)
			$('form#feedback-form input[name="map_state"]').val(FWO.map.getvisiblelayers().join("|"))
			$('form#feedback-form input[name="map_center"]').val(center.lat + "," + center.lng)
			$('form#feedback-form input[name="map_view"]').val(center.lat + "," + center.lng + "," + FWO.map.obj.getZoom())


			/*
                And trigger that call as well when there is a mapmove event while the feedback modal is diplayed.
                */
			FWO.map.obj.on('moveend',function(){
				center = FWO.map.obj.getCenter()
				$('form#feedback-form input[name="map_center"]').val(center.lat + "," + center.lng)
				$('form#feedback-form input[name="map_view"]').val(center.lat + "," + center.lng + "," + FWO.map.obj.getZoom())
			})

 		},
	}
})
