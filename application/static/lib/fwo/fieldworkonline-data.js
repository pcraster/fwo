var FWO=$.extend(FWO || {},{
	uploader:new plupload.Uploader({
		runtimes : 'html5,flash,silverlight,html4',
		browse_button : 'select-files', 
		container: document.getElementById('container'),
		url : upload_url,
		flash_swf_url : '/static/lib/plupload/js/Moxie.swf',
		silverlight_xap_url : '/static/lib/plupload/js/Moxie.xap',
		filters : {
			max_file_size : '10mb',
			mime_types: [
				{title : "Image files", extensions : "jpg,gif,png,jpeg"},
				{title : "Spreadsheets", extensions : "xls,xlsx"},
				{title : "Documents", extensions : "doc,docx,pdf"},
				{title : "Zip files", extensions : "zip"}
			]
		},
		resize: {
			width: 600,
			height: 400
		},
		init: {
			PostInit: function() {
				$('#files-table').html('')
				//$('#upload-files').prop("disabled",true)
				document.getElementById('upload-files').onclick = function() {
					$('#upload-files').prop("disabled",true)
					$('#select-files').prop("disabled",true)
					FWO.uploader.start();
					return false;
				};
				document.getElementById('upload-reset').onclick = function() {
					$('#files-table').html('')
					FWO.uploader.splice();
					return false;
				};
			},
			FilesAdded: function(up, files) {
				$('#upload-files').prop("disabled",false)
				if(!document.getElementById('upload-files-header')) {
					$('#files-table').append('<tr id="upload-files-header"><th style="padding-left:15px;width:30%;">Filename</th><th style="width:15%;">Size</th><th style="width:50%;">Progress</th></tr>')
				}
				plupload.each(files, function(file) {
					var icon="fa-file-o"
					if(file.type.lastIndexOf('image',0)===0) {
						icon="fa-file-image-o"
					}
					$('#files-table').append('<tr id="'+file.id+'"><td style="padding-left:15px;"><i class="fa '+icon+' fa-fw"></i> <code>'+file.name+'</code></td><td>'+plupload.formatSize(file.size)+'<span class="filesize-after" style="color:#aaa;"></span></td><td class="progress-label"><i class="fa fa-clock-o"></i> Waiting in upload queue.</td></tr>')
				});
			},
			UploadProgress: function(up, file) {
				$('tr#'+file.id+" td.progress-label").html('<i class="fa fa-clock-o"></i> Uploading '+file.percent+"%")
				//console.log("total pct:"+uploader.total.percent)
			},
			FileUploaded: function(up, file, response) {
				var resp=jQuery.parseJSON(response.response)
				$('tr#'+file.id+" td.progress-label").html('<i class="fa fa-check-circle"></i> Completed! '+resp['message'])
				if(file.size < file.origSize) {
					$('tr#'+file.id+" span.filesize-after").html(' <i class="fa fa-compress"></i> '+plupload.formatSize(file.size))
				}
			},
			// BeforeUpload: function(up, file) {
			// },
			UploadComplete: function() {
				$('#upload-files').prop("disabled",false)
				$('#select-files').prop("disabled",false)
			},
			Error: function(up, err) {
				if (err.hasOwnProperty("file")) {
					$('tr#'+err.file.id+" td.progress-label").html('<i class="fa fa-exclamation-circle"></i> Failed! <span class="error-message"></span>')
				}
				if (err.hasOwnProperty("response")) {
					response=jQuery.parseJSON(err.response)
					$('tr#'+err.file.id+" td.progress-label span.error-message").html(response['message'])
				} else {
					$('ul#file-errors').append("<li>"+err.message+" (Code "+err.code+")</li>")
				}
			}
		}
	})
})
$(function() {
	FWO.uploader.init()
})

