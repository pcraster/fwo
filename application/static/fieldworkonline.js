// var FWO=$.extend(FWO || {},{
// 	map:{
// 		init:function(){
// 			var controls = ol.control.defaults({rotate: false}).extend([new ol.control.ScaleLine()])
// 			var interactions = ol.interaction.defaults({altShiftDragRotate:false, pinchRotate:false});
// 			var view = new ol.View({center: ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857'),zoom: 11})

// 			FWO.map.obj = new ol.Map({
// 				target: 'map',
// 				layers: [FWO.map.layers.backgroundAerial,FWO.map.layers.backgroundRoad,FWO.map.layers.backgroundWms,FWO.map.layers.qgisServer],
// 				overlays: [FWO.map.overlay],
// 				view: view,
// 				controls: controls,
// 				interactions: interactions
// 			})
// 			FWO.map.obj.on('singleclick',FWO.map.getfeatureinfo)
// 			$('a#popup-closer').click(FWO.map.closefeatureinfo)
// 			$('a.set-background-layer').click(FWO.map.setbackground)
// 			$("a.zoom-to-extent").click(FWO.map.zoom_to_extent)
// 			$('ul#background-layers li a').last().click()
// 			$('[data-toggle="tooltip"]').tooltip()
// 			$("a.layer-visibility-toggle").click(FWO.map.toggle_layer_visibility)
// 			$('form#feedback-form').submit(FWO.feedback.submit)
// 		},
// 		obj: undefined,
// 		overlay: new ol.Overlay({element: document.getElementById('popup')}),
// 		layers:{
// 			backgroundAerial:new ol.layer.Tile({
// 				visible: true,
// 				preload: Infinity,
// 				source: new ol.source.BingMaps({
// 					key: 'ApEqbYdQJSwOJ-KqrCQsI1AAouPQHkng2AjdJsQjLjK55P0yNQc-eEfOLUPUAAMt',
// 					imagerySet: 'Aerial'
// 				})
// 			}),
// 			backgroundRoad:new ol.layer.Tile({
// 				visible: true,
// 				preload: Infinity,
// 				source: new ol.source.BingMaps({
// 					key: 'ApEqbYdQJSwOJ-KqrCQsI1AAouPQHkng2AjdJsQjLjK55P0yNQc-eEfOLUPUAAMt',
// 					imagerySet: 'Road'
// 				})
// 			}),
// 			backgroundWms:new ol.layer.Tile({
// 				visible: true,
// 				source: new ol.source.TileWMS((BACKGROUND_LAYERS))
// 			}),
// 			qgisServer:new ol.layer.Image({
// 				visible: true,
// 				source: new ol.source.ImageWMS({
// 					url: WMS_URL,
// 					params: { 
// 						'LAYERS': window.getVisibleWmsLayers(),
// 						'FORMAT': "image/png; mode=8bit"
// 					}
// 				})
// 			})
// 		},
// 		getfeatureinfo:function(evt) {
// 			/*
// 			FWO.map.getfeatureinfo

// 			Click event on the map. Do a GetFeatureInfo request.
// 			*/
// 			var viewTweak=5; //sets sensitivity of the click area
// 			var viewResolution = (viewTweak*FWO.map.obj.getView().getResolution());
// 			var url = FWO.map.layers.qgisServer.getSource().getGetFeatureInfoUrl(evt.coordinate, viewResolution, 'EPSG:3857',{'INFO_FORMAT': 'application/json'});
// 			if(url) {
// 				//console.log("getFeatureInfo: "+url)
// 				$.ajax({url:url}).done(function(data){
// 					/* fill the popup with data if the request to url completes. */
// 					$('#attribute-values').html("")
// 					var feedback_link='<tr><td colspan="2" style="background-color:#eee;"><a href="javascript:FWO.feedback.show('+evt.coordinate[0]+','+evt.coordinate[1]+')" id="popup-feedback-link">Leave a comment</a></td></tr>'
// 					var html=parseFeatureInfo(data)
// 					var el=$(FWO.map.overlay.getElement())
// 					var tableclass=$("input#checkbox-identify-toplayer-only").is(":checked")?'show-toplayer-only':''

// 					FWO.map.overlay.setPosition(evt.coordinate);
// 					el.find("div#popup-content").html('<table id="popup-attribute-table" class="table table-condensed table-bordered '+tableclass+'" style="margin:0;font-size:0.8em;">'+feedback_link+html+'</table>')
// 					el.show()
// 				})
// 			}
// 		},
// 		closefeatureinfo:function(evt) {
// 			/*
// 			Close the feature info popups
// 			*/
// 			evt.preventDefault()
// 			var link=$(this)
// 			var popup=$(FWO.map.overlay.getElement())
// 			link.blur()
// 			popup.hide()
// 		},
// 		setbackground:function(evt) {
// 			evt.preventDefault()
// 			var link=$(this)
// 			var name=link.data("set-background-layer")
// 			FWO.map.current_background=name
// 			$('ul#background-layers li').each(function(){
// 				li=$(this)
// 				li.removeClass('active')
// 				if (li.attr("id")=="background-layer-"+name) {
// 					li.addClass('active')
// 				}
// 			})
// 			if(name=='bing-aerial') {
// 				FWO.map.layers.backgroundAerial.setVisible(true)
// 				FWO.map.layers.backgroundRoad.setVisible(false)
// 				FWO.map.layers.backgroundWms.setVisible(false)
// 			}
// 			else if(name=='bing-road') {
// 				FWO.map.layers.backgroundAerial.setVisible(false)
// 				FWO.map.layers.backgroundRoad.setVisible(true)
// 				FWO.map.layers.backgroundWms.setVisible(false)
// 			} else {
// 				FWO.map.layers.backgroundAerial.setVisible(false)
// 				FWO.map.layers.backgroundRoad.setVisible(false)
// 				FWO.map.layers.backgroundWms.setVisible(true)
// 				FWO.map.layers.backgroundWms.getSource().updateParams({'LAYERS':name})
// 			}
// 		},
// 		current_background:undefined,
// 		zoom_to_extent:function(evt) {
// 			evt.preventDefault()
// 			var extent=$(this).data("zoom-to-extent").split(",").map(parseFloat)
// 			FWO.map.obj.getView().fitExtent(extent, FWO.map.obj.getSize());
// 		},
// 		toggle_layer_visibility:function(evt) {
// 			evt.preventDefault()
// 			var layer=$(this).parent("li.wms-layer")
// 			if(layer.hasClass("wms-layer-visible")) {
// 				layer.removeClass("wms-layer-visible").addClass("wms-layer-hidden")
// 			} else {
// 				layer.removeClass("wms-layer-hidden").addClass("wms-layer-visible")
// 			}
// 			FWO.map.layers.qgisServer.getSource().updateParams({'LAYERS':window.getVisibleWmsLayers()})
// 			return false;
// 		}
// 	},
// 	feedback:{
// 		map:undefined,
// 		show:function(x,y) {
// 			$('#feedback-modal').modal('show');
// 			$('#comment_body').val("")

// 			var map = FWO.map.obj
// 			var zoom = map.getView().getZoom()
// 			var layers = map.getLayers()
// 			var view = new ol.View({center: [x, y],zoom: zoom})
// 	    	var vectorSource = new ol.source.Vector({'features':[new ol.Feature({geometry:new ol.geom.Point([x,y])})]});

// 		    var iconStyle = new ol.style.Style({
// 		      image: new ol.style.Icon( ({
// 		        anchor: [0.5, 48],
// 		        anchorXUnits: 'fraction',
// 		        anchorYUnits: 'pixels',
// 		        opacity: 1,
// 		        src: '/static/gfx/m2.png'
// 		      }))
// 		    });

// 	    	var vectorLayer = new ol.layer.Vector({source: vectorSource,style: iconStyle});

// 			if(FWO.feedback.map == undefined) {
// 				FWO.feedback.map = new ol.Map({target: 'feedback-map'});
// 			}
// 			FWO.feedback.map.setView(view)
// 			FWO.map.obj.getLayers().forEach(function(lyr,ix,ar){
// 				FWO.feedback.map.addLayer(lyr)
// 			})
// 			FWO.feedback.map.addLayer(vectorLayer)
// 			FWO.feedback.map.on('moveend',function(){
// 				var _mapstate=FWO.map.current_background+"|"+FWO.map.layers.qgisServer.getSource().getParams()['LAYERS']
// 				$('form#feedback-form input[name="map_state"]').val(_mapstate)
// 				$('form#feedback-form input[name="map_center"]').val(FWO.feedback.map.getView().getCenter())
// 				var _view=FWO.feedback.map.getView()
// 				$('form#feedback-form input[name="map_view"]').val(_view.getCenter()+","+_view.getZoom())
// 				$('form#feedback-form input[name="map_marker"]').val(x+","+y)
// 			})
// 		},
// 		submit:function(evt) {
// 			evt.preventDefault()
// 			$.ajax({
// 				type:"POST",
// 				url: $(this).attr('action'),
// 				data: $(this).serialize(),
// 				success: function(data){
// 					$('#feedback-modal').modal('hide');
// 				}
// 			})
// 		}
// 	}
// })
// $(function() {
// 	if(document.getElementById('map') != null) {
// 		FWO.map.init()
// 	}
// })