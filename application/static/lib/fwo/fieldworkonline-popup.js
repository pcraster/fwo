/*
javascript code for making getfeatureinfo popups in a map.
*/
var FWO=$.extend(FWO || {},{
	popup:{
		init:function(map_object){
			/* initializes the popup and links it to the openlayers map instance */
			if(map_object!=undefined) {
				FWO.popup.show_comment_link=document.getElementById('feedback-modal')?true:false
				FWO.popup.map=map_object
				/* add the overlay to the map object */
				FWO.popup.map.addOverlay(FWO.popup.overlay)
				/* attach a click event and call FWO.popup.getfeatureinfo */	
				FWO.popup.map.on('singleclick',FWO.popup.getfeatureinfo)
				/* close the popup when the closer is clicked */
				$('a#popup-closer').click(FWO.popup.closefeatureinfo)
			}
		},
		show_comment_link:false,
		map:undefined,
		overlay:new ol.Overlay({element: document.getElementById('popup')}),
		getfeatureinfo:function(evt){
			var viewTweak=5; //tweaks sensitivity of the click area
			var viewResolution = (viewTweak*FWO.popup.map.getView().getResolution());
			/* 
			we don't know whick layer to query in the map. so, loop through
			the layers and look for the first one whose source has a
			_useForGetFeatureRequests property, then use the getGetFeatureInfoUrl
			function of that layers' source to get a url for the request.
			*/
			var url=""
		    FWO.popup.map.getLayers().forEach(function (lyr) {
		    	if(lyr.hasOwnProperty("_useForGetFeatureRequests")) {
		    		url=lyr.getSource().getGetFeatureInfoUrl(evt.coordinate, viewResolution, 'EPSG:3857',{'INFO_FORMAT': 'application/json'})
		    	}
			})
			var overlay = FWO.popup.overlay
			if(url) {
				$.ajax({url:url}).done(function(data){
					/* fill the popup with data if the request to url completes. */
					$('#attribute-values').html("")
					var feedback_link=""
					if (FWO.popup.show_comment_link) {
						feedback_link='<tr><td colspan="2" style="background-color:#eee;"><a href="javascript:FWO.feedback.show('+evt.coordinate[0]+','+evt.coordinate[1]+')" id="popup-feedback-link">Leave a comment</a></td></tr>'
					}
					var html=FWO.popup.util.parseFeatureInfo(data)
					var el=$(overlay.getElement())
					var tableclass=$("input#checkbox-identify-toplayer-only").is(":checked")?'show-toplayer-only':''
					overlay.setPosition(evt.coordinate);
					el.find("div#popup-content").html('<table id="popup-attribute-table" class="table table-condensed table-bordered '+tableclass+'" style="margin:0;font-size:0.8em;">'+feedback_link+html+'</table>')
					el.show()
				})
			}
		},
		closefeatureinfo:function(evt) {
			/*
			Close the feature info popups
			*/
			evt.preventDefault()
			var link=$(this)
			var popup=$(FWO.popup.overlay.getElement())
			link.blur()
			popup.hide()
		},
		util:{
			/*
			Utility functions & values used for parsing the getfeatredata 
			request data into a pretty looking popup.
			*/
			parseFeatureInfo:function(data) {
				/*
				Returns a block of html to fill the getFeatureInfo popup with.
				*/
				var html=''
				if(data.hasOwnProperty("GetFeatureInfoResponse")) {
					var layers=FWO.popup.util.arrayWrap(data.GetFeatureInfoResponse,"Layer")
					layers.reverse()
					html+=FWO.popup.util.layersToRows(layers)
				}
				return html
			},
			arrayWrap:function(obj,property) {
				/*
				Returns properties of an object wrapped in an array so they can 
				be iterated over. If the property does not exist an empty array is 
				returned (so that any iteration code afterwards still works fine
				as it will just iterate zero times)
				*/
				if(obj.hasOwnProperty(property)) {
					return obj[property] instanceof Array?obj[property]:[obj[property]]
				} else {
					return []
				}
			},
			layersToRows:function(layers) {
				/*
				Turns the layers in the data returned by the getfeatureinfo request
				into table rows containing features.
				*/
				var html=''
				var n=0
				$.each(layers,function(index,layer){
					var features=FWO.popup.util.arrayWrap(layer,"Feature")
					var rows=''
					$.each(features,function(index,feature){
						var feature_attributes=FWO.popup.util.arrayWrap(feature,"Attribute")
						rows+=FWO.popup.util.attributesToRows(feature_attributes)
					})
					var attributes=FWO.popup.util.arrayWrap(layer,"Attribute")
					rows+FWO.popup.util.attributesToRows(attributes)
					if(rows!='') {
						var layer_html_rows="<tr class='__TRCLASS__' style='background-color:#eee;'><td colspan='2'><strong>"+layer["@name"]+"</strong></td></tr>"+rows
						html+=layer_html_rows.replace(/__TRCLASS__/g,(n>0)?'not-top-layer':'')
						n++;
					}
				})
				return html
			},
			attributesToRows:function(attributes) {
				/*
				Returns a html table rows for an array of attributes. This also checks
				for attribute values which may be filenames (such as links to uploaded
				images) as well as HTML links.
				*/
				var html=''
				$.each(attributes,function(index,attribute){
					html+="<tr class='__TRCLASS__'><td><nobr>"+attribute["@name"]+"</nobr></td><td>"+FWO.popup.util.attributeValueParser(attribute["@value"])+"</td></tr>"
				})
				return html
			},
			attributeValueParser:function(value) {
				/*
				Returns a parsed attribute value for in the popup. This checks whether the
				attribute value is a URL, a filename linking to an uploaded attachment, or
				a paragraph of text. Depending on the type of data it will turn it into a 
				link, paragraph, or wrap it in a <code> tag.

				Todo: - change look & feel of large texts. (ie. show a teaser, click to
								open a modal with the full text)
							- check if attachments have been uploaded with a HEAD request, show
								pics in modal and download dialog for other files.
							- check urls using a regex
				*/

				//Valid filename extensions. Ensures that values such as "12.312" are not
				//seen as files.
				var filename_extensions="png jpg txt doc docx xls xlsx jpeg";

				//Text length to turn into a paragraph. If a lot of text is present as an
				//attribute value (such as a detailed description of something) it is
				//better to format it as a paragraph rather than an attribute value in a
				//<code> element.
				var length_max=128;
				var length_truncate=256;

				var filename_regex=/\.([0-9a-z]+)(?:[\?#]|$)/i;
				var filename_list=value.split(",")
				var filename_html=''

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
			entityMap:{ "&": "&amp;","<": "&lt;",">": "&gt;",'"': '&quot;',"'": '&#39;',"/": '&#x2F;' },
			escapeHtml:function(string) {
				return String(string).replace(/[&<>"'\/]/g, function (s) {
					return FWO.popup.util.entityMap[s];
				});
			}
		}
	}
})
$(function() {
	if(typeof FWO.map != 'undefined') {
		FWO.popup.init(FWO.map.obj)
	}
})