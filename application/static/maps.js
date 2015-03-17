
$(function() {

	$("a.layer-visibility-toggle").click(function(){
		layer=$(this).parent("li.wms-layer")
		if(layer.hasClass("wms-layer-visible")) {
			layer.removeClass("wms-layer-visible").addClass("wms-layer-hidden")
		} else {
			layer.removeClass("wms-layer-hidden").addClass("wms-layer-visible")
		}
		wmsLayer.getSource().updateParams({'LAYERS':getVisibleWmsLayers()})
		return false;
	});

	$("a.zoom-to-extent").click(function(){
		extent=$(this).data("zoom-to-extent").split(",").map(parseFloat)
		console.log(extent)
		window.map.getView().fitExtent(extent, window.map.getSize());
		return false;
	})
	$('[data-toggle="tooltip"]').tooltip()

	window.wmsSource=new ol.source.ImageWMS({
		url: WMS_URL,
		params: { 
			'LAYERS': getVisibleWmsLayers(),
			'FORMAT': "image/png; mode=8bit"
		}
	});
	var wmsLayer=new ol.layer.Image({
		source: window.wmsSource
	});
	
	window.tileSource=new ol.source.TileWMS((BACKGROUND_LAYERS));

	window.wmsTileLayer=new ol.layer.Tile({
		//extent: [-13884991, 2870341, -7455066, 6338219],
		source: window.tileSource
	});
	var backgroundLayer=new ol.layer.Tile({
		visible: true,
		preload: Infinity,
		source: new ol.source.BingMaps({
			key: 'ApEqbYdQJSwOJ-KqrCQsI1AAouPQHkng2AjdJsQjLjK55P0yNQc-eEfOLUPUAAMt',
			imagerySet: 'Aerial'
		})
	});
	var wmsView=new ol.View({	
		center: ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857'), /* [-10997148, 4569099], */
		zoom: 11
	});
	/**
	 * Some dom elements that make up the popup.
	 */
	var container = document.getElementById('popup');
	var content = document.getElementById('popup-content');
	var closer = document.getElementById('popup-closer');

	/**
	 * Add a click handler to hide the popup.
	 * @return {boolean} Don't follow the href.
	 */
	closer.onclick = function() {
	  container.style.display = 'none';
	  closer.blur();
	  return false;
	};


	$("a#identify-toplayer-only").click(function(){
		$("input#checkbox-identify-toplayer-only").click()
		return false;
	})
	$("input#checkbox-identify-toplayer-only").change(function(){
		/* change event on the checkbox */
		if($(this).is(":checked")) {
			$("table#popup-attribute-table").addClass("show-toplayer-only")
		} else {
			$("table#popup-attribute-table").removeClass("show-toplayer-only")
		}

	})

	/*
	 * Create an overlay to anchor the popup to the map.
	 */
	var overlay = new ol.Overlay({
	  element: container
	});
	var scaleLineControl = new ol.control.ScaleLine();

	/*
	 * Create the map object as window.map with all the required layers.
	 */
	window.map = new ol.Map({
		target: 'map',
		layers: [backgroundLayer,window.wmsTileLayer,wmsLayer],//wmsLayer,wmsTileLayer
		overlays: [overlay],
		view: wmsView,
		controls: ol.control.defaults().extend([
			new ol.control.ScaleLine()
		])
	});

	/*
	 * Attach a function to open and fill the featureinfo popup to the singleclick
	 * event on the map.
	 */
	map.on('singleclick', function(evt) {
		var viewTweak=5; //sets sensitivity of the click area
		var viewResolution = (viewTweak*wmsView.getResolution());
		var url = wmsSource.getGetFeatureInfoUrl(evt.coordinate, viewResolution, 'EPSG:3857',{'INFO_FORMAT': 'application/json'});
		if(url) {
			console.log("getFeatureInfo: "+url)
			$.ajax({url:url}).done(function(data){
				/* fill the popup with data if the request to url completes. */
				$('#attribute-values').html("")
				var feedback_link='<tr><td colspan="2" style="background-color:#eee;"><a href="javascript:feedbackModal('+evt.coordinate[0]+','+evt.coordinate[1]+')" id="popup-feedback-link">Leave a comment</a></td></tr>'
				var html=parseFeatureInfo(data)
				overlay.setPosition(evt.coordinate);
				tableclass=$("input#checkbox-identify-toplayer-only").is(":checked")?'show-toplayer-only':''
				content.innerHTML = '<table id="popup-attribute-table" class="table table-condensed table-bordered '+tableclass+'" style="margin:0;font-size:0.8em;">'+feedback_link+html+'</table>';
				container.style.display = 'block';
			})
		}
	});


});