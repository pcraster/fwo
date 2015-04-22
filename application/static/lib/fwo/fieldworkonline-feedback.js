/*
    JavaScript for providing the functionality on the feedback page in a user's
    workspace. Everything is stored in the FWO.comments.* variable.
*/
var FWO=$.extend(FWO || {},{
	comments:{
        init:function(comment_id) {
            FWO.comments.reload()
            $("form#comment-reply-form").submit(function(event) {
                event.preventDefault()
                form=$(this)
                console.log("Posting a reply!")
                $.post(form.attr("action"), form.serialize(),function(){
                    sel_comment=parseInt($('#comment-parent').val())
                    FWO.comments.reload(sel_comment)
                })
            })
            FWO.comments.map.init()
        },
        data:[], /* gets filled with data from feedback.json */
        get_comment_by_id:function(id){
            for(var i in FWO.comments.data) {
                if(FWO.comments.data[i].id==id) {
                    return FWO.comments.data[i]
                }
            }
        },
        reload:function(comment_id) {
            $.getJSON("feedback.json", function(data){
                FWO.comments.data=data
                FWO.comments.list.html("")
                $.each(data,function(i){
                    comment=data[i]
                    FWO.comments.list.append('<a href="#" class="list-group-item feedback-link" data-comment-id="'+comment.id+'"><strong>Comment by '+comment.comment_by+'</strong> <span style="float:right;">'+comment.comment_age+' ('+comment.replies.length+' replies)</span><p class="comment-body">'+comment.comment_body.trunc(130)+'</p></a>')
                })
                $('a.feedback-link').click(function(evt){
                    evt.preventDefault()
                    link=$(this)
                    FWO.comments.select_comment(link.data('comment-id'))
                })
                if(typeof comment_id=='undefined') {
                    $('a.feedback-link').first().click()
                } else {
                    FWO.comments.select_comment(comment_id)
                }
                $("#num-comments").html(FWO.comments.data.length)
            })
            $("#reply-body").val("")
        },
        select_comment:function(comment_id) {
            //close any popups
            if(typeof FWO.popup!='undefined') {
                FWO.popup.closefeatureinfo()
            }

            comment=typeof comment_id=='undefined'?FWO.comments.data[0]:FWO.comments.get_comment_by_id(comment_id)
            detail=$('div#comment-detail')
            replies=detail.find('ul#comment-replies')
            $('a.feedback-link').removeClass("active")
            $('a.feedback-link').each(function(){
                link=$(this)
                if(link.data('comment-id')==comment.id) {
                    link.addClass("active")
                }
            })

            detail.find('#comment-body').html(comment.comment_body)
            detail.find('#comment-by').html(comment.comment_by)
            detail.find('#comment-age').html(comment.comment_age)
            detail.find('#comment-parent').val(comment.id)

            replies.html("")
            for(var r in comment.replies) {
                reply=comment.replies[r]
                replies.append('<li class="list-group-item" style="border:none;padding-left:0px;"><strong><i class="fa fa-reply fa-rotate-180 fa-fw"></i> Reply by '+reply.reply_by+'</strong> posted '+reply.comment_age+'<p class="reply-body">'+reply.comment_body+'</p></li>')
            }
            FWO.comments.map.load_comment(comment_id)
            return true;
        },
        list:$('ul#feedback-list'),
        map:{
            background_layer_aerial:new ol.layer.Tile({
                visible: false,
                preload: Infinity,
                source: new ol.source.BingMaps({key: 'ApEqbYdQJSwOJ-KqrCQsI1AAouPQHkng2AjdJsQjLjK55P0yNQc-eEfOLUPUAAMt', imagerySet: 'Aerial'})
            }),
            background_layer_road:new ol.layer.Tile({
                visible: false,
                preload: Infinity,
                source: new ol.source.BingMaps({key: 'ApEqbYdQJSwOJ-KqrCQsI1AAouPQHkng2AjdJsQjLjK55P0yNQc-eEfOLUPUAAMt', imagerySet: 'Road'})
            }),
            background_wms_layer:new ol.layer.Tile({
                visible:false,
                source: new ol.source.TileWMS((BACKGROUND_LAYERS))
            }),
            foreground_wms_layer:new ol.layer.Image({
                source: new ol.source.ImageWMS({
                    visible:false,
                    url: WMS_URL,
                    params: { 'LAYERS': "" }
                })
            }),
            obj:new ol.Map({
                target: 'commentmap',
                layers: [],
                view: new ol.View({	
                    center: ol.proj.transform([5.721586,44.42], 'EPSG:4326', 'EPSG:3857'),
                    zoom: 11
                }),
                controls: ol.control.defaults().extend([
                    new ol.control.ScaleLine()
                ])
            }),
            init:function(){
                FWO.comments.map.foreground_wms_layer._useForGetFeatureRequests=true
                FWO.comments.map.obj.addLayer(FWO.comments.map.background_layer_aerial)
                FWO.comments.map.obj.addLayer(FWO.comments.map.background_layer_road)
                FWO.comments.map.obj.addLayer(FWO.comments.map.background_wms_layer)
                FWO.comments.map.obj.addLayer(FWO.comments.map.foreground_wms_layer)
                FWO.comments.map.obj.addLayer(FWO.comments.map.point_as_layer())
            },
            load_comment:function(comment_id) {
                comment=FWO.comments.get_comment_by_id(comment_id)

                var map_state=comment.map_state.split("|")
                var layers_background=""
                var layers_foreground=""
                if (map_state.length == 2) {
                    layers_background=map_state[0]
                    layers_foreground=map_state[1]
                } else {
                    layers_background=""
                    layers_foreground=map_state
                }
                layers_background=layers_background==""?"bing-aerial":layers_background

                if (layers_background=="bing-aerial") {
                    FWO.comments.map.background_layer_aerial.setVisible(true)
                    FWO.comments.map.background_layer_road.setVisible(false)
                    FWO.comments.map.background_wms_layer.setVisible(false)
                } else if (layers_background=="bing-road") {
                    FWO.comments.map.background_layer_aerial.setVisible(false)
                    FWO.comments.map.background_layer_road.setVisible(true)
                    FWO.comments.map.background_wms_layer.setVisible(false)
                } else {
                    FWO.comments.map.background_layer_aerial.setVisible(false)
                    FWO.comments.map.background_layer_road.setVisible(false)
                    FWO.comments.map.background_wms_layer.setVisible(true)
                    FWO.comments.map.background_wms_layer.getSource().updateParams({'LAYERS':layers_background})    
                }
                if (layers_foreground!="") {
                    FWO.comments.map.foreground_wms_layer.setVisible(true)
                    FWO.comments.map.foreground_wms_layer.getSource().updateParams({'LAYERS':layers_foreground})
                } else {
                    FWO.comments.map.foreground_wms_layer.setVisible(false)
                }

                var _xyz=comment.map_view.split(",")
				FWO.comments.map.obj.setView(
					new ol.View({	
				 		center: [parseFloat(_xyz[0]),parseFloat(_xyz[1])],
				 		zoom: parseInt(_xyz[2])
					})
				);
                FWO.comments.map.move_marker_to(comment.map_marker)
            },
            move_marker_to:function(coord) {
			    FWO.comments.map.obj.getLayers().forEach(function (lyr) {
					if(lyr.hasOwnProperty("_fwid")) {
						if(lyr._fwid=="marker") {
							//this is the marker layer. just remove it, we'll add a new one rght after.
							FWO.comments.map.obj.removeLayer(lyr)
						}
					}
				});
			    var _xy=coord.split(",")
			    var _newlyr=FWO.comments.map.point_as_layer([parseFloat(_xy[0]),parseFloat(_xy[1])])
                FWO.comments.map.obj.addLayer(_newlyr)
            },
			point_as_layer:function(coord) {
				/* returns a ready made vector layer with a single point. this saves
				   some hassle with trying to grab the point and move it. */
				if(coord) {
					features=[new ol.Feature({geometry:new ol.geom.Point(coord)})]
				} else {
					features=[]
				}
				var vectorSource = new ol.source.Vector({
		    		'features':features,
		    		'projection':'EPSG:4326'
		    	});
			    var iconStyle = new ol.style.Style({
			      image: new ol.style.Icon( ({
			        anchor: [0.5, 48],
			        anchorXUnits: 'fraction',
			        anchorYUnits: 'pixels',
			        opacity: 1,
			        src: '/static/gfx/m2.png'
			      }))
			    });
			    _lyr=new ol.layer.Vector({source: vectorSource,style: iconStyle});
			    _lyr._fwid="marker"
			    return _lyr
			}
        }
    }
})
$(function() {
	FWO.comments.init()
})


/*
	Function for truncating strings
*/
String.prototype.trunc = String.prototype.trunc ||
	function(n){
		return this.length>n ? this.substr(0,n-1)+'&hellip;' : this;
	};