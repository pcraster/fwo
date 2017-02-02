/*
Javascript code for showing the main map in a users' workspace. All the map related
code is in FWO.map.*, the actual OpenLayers map instance is FWO.map.obj.

Functionality for leaving feedback is located in FWO.feedback.*.
*/
var FWO=$.extend(FWO || {},{
	config:{},
	map:{
		fetch_map:function(url) {
			$.ajax({
				type: "GET",
				url: url,
				success: function(data) {
					
					FWO.map._layers = FWO.map.json_to_layers(data)

					FWO.map.init()
					
					FWO.map.update_from_state()

				},
				error: function() {
					alert("Could not load map!")
				}
			})
		},
		init:function(){
			/*
			FWO.map.init()

			Initialize the fieldwork online map in a user's workspace.
			*/
			
			FWO.map.BackgroundLayer = new L.LayerGroup()
			FWO.map.VisibleLayers = new L.LayerGroup()
			
			for (layer in FWO.map._layers.data) {
				FWO.map.VisibleLayers.addLayer(FWO.map._layers['data'][layer])
				}

			/*
			Create the map object in FWO.map.obj. This is the Leaflet map instance
			that will hold the actual map.
			*/
			FWO.map.obj = L.map('map', {
				layers: [FWO.map.VisibleLayers, FWO.map.BackgroundLayer],
				center: [5.721586,44.42],
				zoom: 4
			})

			/* Attach a click event to the background links for changing the background map */
			$('a.set-background-layer').click(function(){
				var name = $(this).data("set-background-layer")
				$(this).blur()
				$("ul#background-layers li").removeClass('active')
				$("li#background-layer-"+name).addClass('active')
				FWO.map.setbackground(name)
			})
			$('ul#background-layers li a').last().click()

			/* 
			Call FWO.map.datalayer_toggle_visibility when one of the visibility links is clicked 
			*/
			$("a.layer-visibility-toggle").click(function(){
				var el=$(this).parent("li")
				var name=el.data("layer-name")
				var is_visible=FWO.map.datalayer_toggle_visibility(name)
				var li = $("li#userdata-layers-"+name)
				if(li) {
					if(is_visible) {
						li.removeClass("wms-layer-visible").addClass("wms-layer-hidden")
					} else {
						li.removeClass("wms-layer-hidden").addClass("wms-layer-visible")
					}
				}
			});

			/* 
			Add a click event handler to the "zoom-to-extent" links for each layer (the magnifying
			glass)
			*/
			$("a.zoom-to-extent").click(function(){
				var el=$(this).parent("li")
				var name=el.data("layer-name")
				FWO.map.datalayer_zoom_to(name)
			});

			/*
			Check if the feedback script is loaded.
			*/
			if("feedback" in FWO) {
				/*
				Add a click event handler to the "leave a comment" link within popups. It uses the links'
				data-location-x and data-location-y attributes to get the location.
				*/
				$("a#popup-leave-comment").click(function(){
					var el=$(this)
					var coord=el.data("location")
					FWO.feedback.show(coord)
				});			
				/*
				Add a "submit" event handler to the feedback form to call FWO.feedback.submit when the
				"submit feedback" button is clicked.
				*/
				$("form#feedback-form").submit(FWO.feedback.submit)
			} else {
				/*
				
				*/
				$("a#popup-leave-comment").hide()
			}

			/*
			Initialize any bootstrap tooltips which may exist on the page.
			*/
			$('[data-toggle="tooltip"]').tooltip()
		},
		getlayerbyname:function(name) {
			/*
			FWO.map.getlayerbyname(name)
			
			takes a name, passes the layer
			*/
			for(var layergroup in FWO.map._layers) {
				if(Object.prototype.hasOwnProperty.call(FWO.map._layers[layergroup], name)) {
					return FWO.map._layers[layergroup][name]
				}
			}
			return false;
		},
		getvisiblelayers:function() {
			/*
			FWO.map.getvisiblelayers()

			Returns a list of layer names which are visible.
			
			Visible.getLayers()
			*/
			var visible_layers = []
			for(var layergroup in FWO.map._layers) {
				for(var layername in FWO.map._layers[layergroup]) {
					var layer = FWO.map._layers[layergroup][layername]
					if(FWO.map.VisibleLayers.hasLayer(layer)) {
						visible_layers.push(layername)
					}
				}
			}
			return visible_layers;
		},
		setvisiblelayers:function(visible_layers) {
			/*
			FWO.map.setvisiblelayers()

			Hides all layers except the ones passed in visible_layers
			
			Visible.clearLayers()
			for layer in visible_layers: Visible.addLayer(layer)
			*/
			FWO.map.VisibleLayers.clearLayers()
			for(var layergroup in FWO.map._layers) {
				for(var layername in layergroup) {
					var layer = FWO.map._layers[layergroup][layername]
					var inArray = $.inArray(layername,visible_layers)
					if (inArray != -1) {
						FWO.map.VisibleLayers.addLayer(layer)
					}
				}
			}
		},
		setbackground:function(name) {
			/*
			FWO.map.setbackground()

			Set the background of the map
			
			
			*/
			var layer = FWO.map.getlayerbyname(name)
			FWO.map.BackgroundLayer.clearLayers()
			FWO.map.BackgroundLayer.addLayer(layer)
		},
		datalayer_zoom_to:function(name) {
			/*
			FWO.map.datalayer_zoom_to()

			Zoom to the extent of one of the data layers
			*/
			var layer = FWO.map.getlayerbyname(name)
			FWO.map.obj.fitBounds(layer.getBounds(), {padding: [0.5, 0.5]})
			
		},
		datalayer_toggle_visibility:function(name) {
			/*
			FWO.map.datalayer_toggle_visibility()

			Toggle the visibility of one of the data layers
			*/
			var layer = FWO.map.getlayerbyname(name)
			var is_visible = FWO.map.VisibleLayers.hasLayer(layer)
			if(is_visible) {
				FWO.map.VisibleLayers.removeLayer(layer) 
			}
			else {
				FWO.map.VisibleLayers.addLayer(layer)
			}
			return is_visible
			
		},
		json_to_layers:function(data) {
			/*
			FWO.map.json_to_layers() 

			Convert json data created by the "project_data_maplayers" view to OpenLayers map
			layers which can be added to the map.
			*/
			var layers = {
				'background' : {},
				'wms' : {},
				'data' : {}	
				}
			for(var i=0; i<data.layers.length; i++) {
				(function(i) {
					var layer = data.layers[i];
					var layername = layer['name']
					var new_layer = undefined
					var geojson = undefined
					/*
					For MQ road and satellite layers. 
					*/
					if(layer['type'] == 'background') {
						new_layer = new MQ.mapLayer();
						options = ['map', 'hyb', 'sat', 'light', 'dark']
						if (options.indexOf(layername) > -1) {new_layer.setMapType(layername)}
						if (new_layer instanceof L.Layer) {
							layers.background[layername] = new_layer
							}
					}
					/* 
					For WMS layers representing a BackgroundLayer.
					L.TileLayer.WMS()
					Nog niet getest
					*/
					if(layer['type'] == 'wms') {
						layer_url = layer['attributes']['mapserver_url']+'?&map='+layer['attributes']['mapserver_mapfile']
						new_layer = L.tileLayer.wms(layer_url, {
							layers: layer['attributes']['mapserver_layer'],
							format: 'image/png'
						})
						if (new_layer instanceof L.Layer) {
							layers.wms[layername] = new_layer
							}
					}

					/*
					For geojson layers with Observations in it.
					*/
					
					if(layer['type'] == 'geojson') {
						new_layer = new L.geoJSON(null, {
								pointToLayer: function (feature, latlng) {
									var new_style = {
										radius: 5,
										fillColor: layer['attributes']['color'],
										color: '#000000',
										weight: 0,
										opacity: 1,
										fillOpacity: 1
									}
									return L.circleMarker(latlng, new_style).addTo(layers.data[layername]);
								},
								onEachFeature: function (feature, point) {
									point.bindPopup(FWO.util.feature2popup(feature), {
										autoPan: true,
										maxHeight: 200,
										minWidth: 300
										});
									/*point.setStyle(function(feature) {
										fillColor: FWO.util.getColor(feature);
									});*/	
								}
							})
						$.getJSON(layer['attributes']['url'], function (res) {
							new_layer.addData(res)});
						if (new_layer instanceof L.Layer) {
							layers.data[layername] = new_layer
						}
					}
				})(i)
			}
			return layers
		},
		update_from_state:function() {
			/*
			FWO.map.update_for_comment()

			Function for updating the map state to match a specific state at the
			time a comment was made. Takes three strings (state, view, and a 
			marker location)
			*/
			if("map_state" in FWO.config) {
				/*
				Update the visible layers.
				*/
				var visible_layers = FWO.config["map_state"].split("|")
				console.log(visible_layers)
				FWO.map.setvisiblelayers(visible_layers)
			}
			if("map_view" in FWO.config) {
				/*
				Update the map view.
				*/
				var xyz = FWO.config["map_view"].split(",")
				FWO.map.obj.setView([parseFloat(xyz[0]),parseFloat(xyz[1])], parseInt(xyz[2]));
			}
			if("map_marker" in FWO.config) {
				/*
				Update the map marker.
				*/
				var xy = FWO.config["map_marker"].split(",")
				var icon = new L.Icon({iconUrl: '/static/gfx/m2.png', iconAnchor: [24, 48]});
				var layer = new L.Marker([parseFloat(xy[0]),parseFloat(xy[1])], {icon: icon});
				FWO.map.obj.addLayer(layer)
			}
		}
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
			var html="<div id='popup' class='ol-popup' style='display:block;'>"+
					"<div id='popup-header' style='height:25px;'>"+
					"<a id='popup-leave-comment' href='#' data-location=''>Leave comments or feedback</a>"+
					"<span id='popup-title'></span>"+
					"<a href='#' id='popup-closer' class='ol-popup-closer'><i class='fa fa-times'></i></a>"+
					"</div>"+
					"<div id='popup-content'><table class='table table-condensed' style='width:100%;font-size:10pt;margin-bottom:0px;'>"
			if(feature) {
				var prop=feature.properties
				for(var i in prop) {
					var val=prop[i]
					if(typeof val=='string' || typeof val=='number') {
						val=val+""
						html+="<tr><td style='padding-left:0px;'>"+i+"</td><td>"+FWO.util.attributeValueParser(val)+"</td></tr>"
					}
				}
			} else {
				html+="<tr><td colspan='2' style='padding-top:18px;padding-bottom:15px;text-align:center;'>No features were identified at this location.</td></tr>"
			}
			return html+"</div></div></div></table>"
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
						return "<p>"+FWO.util.escapeHtml(value)+"</p>"
				} else {
					value=""+value
					return "<code>"+FWO.util.escapeHtml(value)+"</code>"
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
})
