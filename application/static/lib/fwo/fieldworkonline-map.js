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

					FWO.popup.init()
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

			/*
			Create the map controls. These will be added to the map instance later.
			*/
			var controls = ol.control.defaults({rotate: false}).extend([new ol.control.ScaleLine()])
			var interactions = ol.interaction.defaults({altShiftDragRotate:false, pinchRotate:false});
			var view = new ol.View({center: ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857'),zoom: 11})

			/*
			Create the map object in FWO.map.obj. This is the OpenLayers map instance
			that will hold the actual map.
			*/
			FWO.map.obj = new ol.Map({
				target: 'map',
				layers: FWO.map._layers,
				overlays: [],
				view: view,
				controls: controls,
				interactions: interactions
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
					li.removeClass("wms-layer-hidden").addClass("wms-layer-visible")
				} else {
					li.removeClass("wms-layer-visible").addClass("wms-layer-hidden")
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
		//obj: undefined,
		//overlay: new ol.Overlay({element: document.getElementById('popup')}),
		/*
		layers:{
			backgroundAerial:new ol.layer.Tile({
				visible: true,
				preload: Infinity,
				source: new ol.source.BingMaps({
					key: window.BINGMAPS_KEY,
					imagerySet: 'Aerial'
				})
			}),
			backgroundRoad:new ol.layer.Tile({
				visible: true,
				preload: Infinity,
				source: new ol.source.BingMaps({
					key: window.BINGMAPS_KEY,
					imagerySet: 'Road'
				})
			}),
			backgroundWms:new ol.layer.Tile({
				visible: true,
				source: new ol.source.TileWMS((BACKGROUND_LAYERS))
			}),
			qgisServer:new ol.layer.Image({
				visible: true,
				source: new ol.source.ImageWMS({
					url: WMS_URL,
					params: { 
						'LAYERS': window.getVisibleWmsLayers(),
						'FORMAT': "image/png; mode=8bit"
					}
				})
			})
		},
		*/
		getlayerbyname:function(name) {
			for(var i=0; i<FWO.map._layers.length; i++) {
				if(FWO.map._layers[i]["_name"] == name) {
					return FWO.map._layers[i]
				}
			}
			return false;
		},
		getvisiblelayers:function() {
			/*
			FWO.map.getvisiblelayers()

			Returns a list of layer names which are visible.
			*/
			var visible_layers = []
			for(var i=0; i<FWO.map._layers.length; i++) {
				if("_name" in FWO.map._layers[i]) {
					if(FWO.map._layers[i].getVisible()) {
						visible_layers.push(FWO.map._layers[i]._name)
					}
				}
			}
			return visible_layers;
		},
		setvisiblelayers:function(visible_layers) {
			/*
			FWO.map.setvisiblelayers()

			Hides all layers except the ones passed in visible_layers
			*/
			for(var i=0; i<FWO.map._layers.length; i++) {
				if("_name" in FWO.map._layers[i]) {
					var layer = FWO.map._layers[i]
					var inArray = $.inArray(layer["_name"],visible_layers)
					layer.setVisible(inArray != -1 ? true : false)
				}
			}
		},
		setbackground:function(name) {
			/*
			FWO.map.setbackground()

			Set the background of the map
			*/
			for(var i=0; i<FWO.map._layers.length; i++) {
				var layer = FWO.map._layers[i]
				if("_type" in layer) {
					if(layer["_type"] == 'background' || layer["_type"] == 'wms') {
						layer.setVisible(layer["_name"]==name?true:false) 
					}
				}
			}
		},
		datalayer_zoom_to:function(name) {
			/*
			FWO.map.datalayer_zoom_to()

			Zoom to the extent of one of the data layers
			*/
			var layer = FWO.map.getlayerbyname(name)
			var extent = layer.getSource().getExtent()
		 	FWO.map.obj.getView().fitExtent(extent, FWO.map.obj.getSize())
		},
		datalayer_toggle_visibility:function(name) {
			/*
			FWO.map.datalayer_toggle_visibility()

			Toggle the visibility of one of the data layers
			*/
			var layer = FWO.map.getlayerbyname(name)
			layer.setVisible(layer.getVisible() ? false : true)
			return layer.getVisible()
		},
		json_to_layers:function(data) {
			/*
			FWO.map.json_to_layers() 

			Convert json data created by the "project_data_maplayers" view to OpenLayers map
			layers which can be added to the map.
			*/
			var layers = []
			for(var i=0; i<data.layers.length; i++) {
				var layer = data.layers[i];
				var new_layer = undefined
				/*
				For bing road and bing aerial layers.
				*/
				if(layer['type'] == 'background') {
					new_layer = new ol.layer.Tile({
						visible: false,
						preload: Infinity,
						source: new ol.source.MapQuest({layer: 'osm'})
					});
				}
				/* 
				For WMS layers representing a BackgroundLayer.
				*/
				if(layer['type'] == 'wms') {
					new_layer = new ol.layer.Tile({
						visible: false,
						source: new ol.source.TileWMS(({
							url: layer['attributes']['mapserver_url'],
							params: {
								'LAYERS':layer['attributes']['mapserver_layer'],
								'TILED': true,
								'MAP':layer['attributes']['mapserver_mapfile'],
								'FORMAT':'image/png; mode=8bit' //image/png; mode=8bit
							},
							serverType: 'mapserver'
						}))
					})
				}

				/*
				For geojson layers with Observations in it.
				*/
				if(layer['type'] == 'geojson') {
					new_layer = new ol.layer.Vector({
						visible: true,
						source: new ol.source.GeoJSON({
							projection : 'EPSG:3857',
							preFeatureInsert: function(feature) { feature.geometry.transform('EPSG:4326', 'EPSG:3857') },
							url:layer['attributes']['url']
						}),
						style: new ol.style.Style({
							image: new ol.style.Circle({
								radius: 4,
								fill: new ol.style.Fill({color:layer['attributes']['color'],opacity: 0.6}),
								stroke: new ol.style.Stroke({color: 'black', width: 1, opacity:0.5})
							})
						})
					});
				}
				/*
				Only add the new layer to the layers variable when it is actually an instance of an
				OpenLayers tile or vector layer.
				*/
				if(new_layer instanceof ol.layer.Vector || new_layer instanceof ol.layer.Tile) {
					new_layer._name = layer['name'] //Add a _name attribute to the layer so that we can find it again using FWO.map.getlayerbyname()
					new_layer._type = layer['type']
					layers.push(new_layer)
				}
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
				var view = new ol.View({ center: [parseFloat(xyz[0]),parseFloat(xyz[1])], zoom: parseInt(xyz[2]) })
				FWO.map.obj.setView(view);
			}
			if("map_marker" in FWO.config) {
				/*
				Update the map marker.
				*/
				var xy = FWO.config["map_marker"].split(",")
				var vectorSource = new ol.source.Vector({ 'features':[new ol.Feature({geometry:new ol.geom.Point([parseFloat(xy[0]),parseFloat(xy[1])])})], 'projection':'EPSG:4326' });
				var iconStyle = new ol .style.Style({ image: new ol.style.Icon( ({ anchor: [0.5, 48], anchorXUnits: 'fraction', anchorYUnits: 'pixels', opacity: 1, src: '/static/gfx/m2.png' })) });
				var layer = new ol.layer.Vector({source: vectorSource, style: iconStyle});
				FWO.map.obj.addLayer(layer)
			}
		}
	}
})
