
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
	/*
	$("a.layer-active-toggle").click(function(){
		$("li.wms-layer").removeClass("wms-layer-active")
		layer=$(this).parent("li.wms-layer")
		layer.addClass("wms-layer-active")
		return false;
	});
	*/
	$("a.zoom-to-extent").click(function(){
		extent=$(this).data("zoom-to-extent").split(",").map(parseFloat)
		console.log(extent)
		window.map.getView().fitExtent(extent, window.map.getSize());
		return false;
	})
	$('[data-toggle="tooltip"]').tooltip()

	var wmsSource=new ol.source.ImageWMS({
		url: WMS_URL,
		params: { 'LAYERS': getVisibleWmsLayers(), 'map': WMS_MAP }
	});
	var wmsLayer=new ol.layer.Image({
		//extent: [-13884991, 2870341, -7455066, 6338219],
		source: wmsSource
	});
	var backgroundLayer=new ol.layer.Tile({
		visible: true,
		preload: Infinity,
		source: new ol.source.BingMaps({
			key: 'ArrQ3XQLuE1VvgE3YKKvKQb5qxlkDirR2teUad8p9eG9lvvfIfbjf-S2pPb-hF6c',
			imagerySet: 'Aerial'
		})
	});
	var wmsView=new ol.View({	
		center: ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857'), /* [-10997148, 4569099], */
		zoom: 11
	});
/**
 * Elements that make up the popup.
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


/**
 * Create an overlay to anchor the popup to the map.
 */
var overlay = new ol.Overlay({
  element: container
});
var scaleLineControl = new ol.control.ScaleLine();

window.map = new ol.Map({
	target: 'map',
	layers: [backgroundLayer,wmsLayer],
	overlays: [overlay],
	view: wmsView,
	controls: ol.control.defaults().extend([
		new ol.control.ScaleLine()
	])
});


//ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857')
//ex=ol.extent.boundingExtent([ol.proj.transform([2.,2.], 'EPSG:4326', 'EPSG:3857'),ol.proj.transform([11.,11.], 'EPSG:4326', 'EPSG:3857')])
//map.getView().fitExtent(ex, map.getSize());



map.on('singleclick', function(evt) {
	var viewTweak=5;//set sensitivity of the click area
	var viewResolution = (viewTweak*wmsView.getResolution());
	var url = wmsSource.getGetFeatureInfoUrl(evt.coordinate, viewResolution, 'EPSG:3857',{'INFO_FORMAT': 'application/json'});
	if(url) {
		console.log("getFeatureInfo: "+url)
		$.ajax({url:url}).done(function(data){
			

			//empty the attribute value list
			$('#attribute-values').html("")

			//collapse all the things

			var html=parseFeatureInfo(data)
/*
			$(data).find("Layer").each(function(){
				layer=$(this)
				feats=layer.find("Feature")

				

				$('#attribute-values').append('<li class="list-group-item"><i class="fa fa-th fa-fw"></i> <a href="#">'+layer.attr("name")+'</a></li>')
				if(feats.length>0) {
					
					attrs=feats.find("Attribute")
					if(attrs.length>0) {
						html+="<tr style='background-color:#eee;'><td colspan='2'><strong>"+layer.attr("name")+"</strong></td></tr>"
						attrs.each(function(){
							attr=$(this)
							html+="<tr><td>"+attr.attr("name")+"</td><td><code>"+attr.attr("value")+"</code></td></tr>"
						})
					}
				} else {
					attrs=layer.find("Attribute")
					if(attrs.length>0) {
						html+="<tr style='background-color:#eee;'><td colspan='2'><strong>"+layer.attr("name")+"</strong></td></tr>"
						attrs.each(function(){
							attr=$(this)

							html+="<tr><td>"+attr.attr("name")+"</td><td><code>"+attr.attr("value")+"</code></td></tr>"
						})
					} else {
						//html+="<tr><td colspan='2'>No hits found!</td></tr>"
					}
				}


			})*/
			overlay.setPosition(evt.coordinate);
			content.innerHTML = '<table class="table table-condensed table-bordered" style="margin:0;margin-top:17px;font-size:0.8em;">'+html+'</table>';
			container.style.display = 'block';

			/*if($('#accordion #collapseSix').hasClass("in")) {

			} else {
				$('#accordion div.in').collapse('hide');
				$('#accordion #collapseSix').collapse('show');
			}*/
			//console.log(data)
		})
	}
  // if (url) {
  //   document.getElementById('info').innerHTML =
  //       '<iframe seamless src="' + url + '"></iframe>';
  // }
});


});