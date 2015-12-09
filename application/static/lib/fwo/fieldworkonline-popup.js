/*
Code for making feature popups in the main map. All the code for the feature popups
lives in FWO.popup.*
*/
var FWO=$.extend(FWO || {},{
	popup:{
		init:function(){
			/*
			FWO.popup.init()

			Initialize the popups.
			*/

			/* Create the OpenLayers overlay */
			FWO.map.overlay = new ol.Overlay({element: document.getElementById('popup')});

			/* Add the overlay to the map object. The overlay holds the popup */
			FWO.map.obj.addOverlay(FWO.map.overlay)
			
			/* Attach a click event and to the main map, and call FWO.popup.getfeatureinfo() when it is clicked */
			FWO.map.obj.on('singleclick', FWO.popup.getfeatureinfo)

			/* Attach a click event to the a#popup-closer link that closes the popup by setting the overlay position to undefined */
			$('a#popup-closer').click(function(){
				$(this).blur() //Blur the link
				FWO.map.overlay.setPosition(undefined); //Kill the overlay
			})
		},
		getfeatureinfo:function(evt){
			console.log("getfeatureinfo!")
			/*
			Identify the feature that was clicked using forEachFeatureAtPixel on the map object
			*/
			var feature = FWO.map.obj.forEachFeatureAtPixel(evt.pixel,function(feature, layer) {return feature;});
			console.log(feature)
			/*
			Determine the coordinates where the popup should be anchored 
			*/
			var coord = feature ? feature.getGeometry().getCoordinates() : evt.coordinate;

			/*
			Fill the popup content with the output of feature2popup
			*/
			var popup_html = FWO.popup.util.feature2popup(feature)
			$("div#popup-content").html(popup_html)

			/*
			Set the location-x and location-y attributes of the "Leave a comment" link, so in case the 
			user ends up clicking it, we'll know where to position the comment.
			*/
			var comment_link = $("a#popup-leave-comment")
			comment_link.data("location",coord)

			/*
			Display the overlay.
			*/
			FWO.map.overlay.setPosition(coord)
		},
		util:{
			/*
			Utility functions & values used for parsing the getfeatredata 
			request data into a pretty looking popup.
			*/
			feature2popup:function(feature) {
				/*
				FWO.popup.util.feature2popup()

				Convert a feature to a bunch of HTML that can be inserted in a map popup.
				*/
				var html="<table class='table table-condensed' style='width:100%;font-size:10pt;margin-bottom:0px;'>"
				if(feature) {
					var prop=feature.getProperties()
					for(var i in prop) {
						var val=prop[i]
						if(typeof val=='string' || typeof val=='number') {
							val=val+""
							html+="<tr><td style='padding-left:0px;'>"+i+"</td><td>"+FWO.popup.util.attributeValueParser(val)+"</td></tr>"
						}
					}
				} else {
					html+="<tr><td colspan='2' style='padding-top:18px;padding-bottom:15px;text-align:center;'>No features were identified at this location.</td></tr>"
				}
				return html+"</table>"
			},
			attributeValueParser:function(value) {
				/*
				FWO.popup.util.attributeValueParser()

				Returns a parsed attribute value for in the popup. This checks whether the
				attribute value is a URL, a filename linking to an uploaded attachment, or
				a paragraph of text. Depending on the type of data it will turn it into a 
				link, paragraph, or wrap it in a <code> tag.

				Todo: - change look & feel of large texts. (ie. show a teaser, click to
								open a modal with the full text)
							- check if attachments have been uploaded with a HEAD request, show
								pics in modal and download dialog for other files.
							- check urls using a regex

							- PHOTOS... use FWO.util.photomodal() instaed of current one.
				*/

				/*
				Define valid filename extensions. Ensures that values such as "12.312" are not
				seen as files.
				*/
				var filename_extensions="png jpg txt doc docx xls xlsx jpeg";
				var filename_regex=/\.([0-9a-z]+)(?:[\?#]|$)/i;
				var filename_list=value.split(",")
				var filename_html=''

				/*
				Minimum text length to turn into a paragraph. If a lot of text is present as an
				attribute value (such as a detailed description of something) it is better to 
				format it as a paragraph rather than an attribute value in a <code> element.
				*/
				var length_max=128;
				var length_truncate=256;

				$.each(filename_list,function(index,filename){
					var filename_match=filename.match(filename_regex);
					if(filename_match) {
						var filename_extension=filename_match[1].toLowerCase()
						if($.inArray(filename_extension,filename_extensions.split(" "))!=-1) {
							var is_image=(filename_extension=='png' || filename_extension=='jpeg' || filename_extension=='jpg')?true:false;
							var filename_url="file?filename="+filename;
							if(is_image){
								filename_html+= "<i class='fa fa-photo'></i> <code><a href='#' onclick=\"photoModal('"+filename_url+"')\" class='disabled'>"+filename+"</a></code><br/>"
							} else {
								filename_html+= "<i class='fa fa-paperclip'></i> <code><a href='"+filename_url+"' class='disabled' target='_blank'>"+filename+"</a></code><br/>"
							}
						}
					}
				})
				if(filename_html=='') {
					if(value.length>length_max) {
							value=""+value
							return "<p>"+FWO.popup.util.escapeHtml(value)+"</p>"
					} else {
						value=""+value
						return "<code>"+FWO.popup.util.escapeHtml(value)+"</code>"
					}
				} else {
					return filename_html
				}
			},
			escapeHtml:function(string) {
				/*
				FWO.popup.util.escapeHtml()

				Escapes HTML code to turn it into a string we can display in the document.
				*/
				var entityMap = { "&": "&amp;","<": "&lt;",">": "&gt;",'"': '&quot;',"'": '&#39;',"/": '&#x2F;' };
				return String(string).replace(/[&<>"'\/]/g, function (s) {
					return entityMap[s];
				});
			}
		}
	}
})
