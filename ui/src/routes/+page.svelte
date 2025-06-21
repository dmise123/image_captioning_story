<script>
	import { onMount } from 'svelte';
	import 'carbon-components-svelte/css/white.css';
	import Upload from "carbon-icons-svelte/lib/Upload.svelte";
	import CameraAction from "carbon-icons-svelte/lib/CameraAction.svelte";
	import Reset from "carbon-icons-svelte/lib/Reset.svelte";
	import {
		Content,
		Grid,
		Row,
		Column,
		FileUploader,
		Button,
		Loading,
		RadioButtonGroup,
		RadioButton,
		InlineNotification,
		Tile,
		SkeletonText,
		SkeletonPlaceholder
	} from 'carbon-components-svelte';

	// State variables
	let selectedFile = null;
	let previewUrl = null;
	let loading = false;
	let caption = '';
	let errorMessage = '';
	let showResult = false;
	
	// Model selection
	const models = ["RNN with Attention", "Vision Transformer"];
	const modelMap = {
		"RNN with Attention": "rnn_attention",
		"Vision Transformer": "vision_transformer"
	};
	let selectedModel = models[0];	// Handle file selection
	function handleFileSelect(event) {
		console.log('File upload event:', event);
		
		try {
			// Carbon components can send different event structures
			let files = [];
			
			if (event.target && event.target.files) {
				// Standard DOM file input
				files = Array.from(event.target.files);
			} else if (event.detail) {
				// Carbon component custom event
				const detail = event.detail;
				
				if (Array.isArray(detail)) {
					files = detail;
				} else if (detail.files) {
					files = Array.from(detail.files);
				} else if (detail.file) {
					files = [detail.file];
				} else if (detail instanceof File) {
					files = [detail];
				}
			}
			
			// Process the first file
			if (files && files.length > 0) {
				const file = files[0];
				
				if (file instanceof File) {
					selectedFile = file;
					previewUrl = URL.createObjectURL(file);
					
					// Reset previous results
					caption = '';
					showResult = false;
					errorMessage = '';
					
					console.log('File selected:', file.name, file.type, file.size);
				} else {
					throw new Error('Invalid file object');
				}
			} else {
				throw new Error('No files found in event');
			}
		} catch (error) {
			console.error('Error handling file:', error);
			errorMessage = 'Error processing the selected file. Please try again.';
		}
	}

	// Handle file drag rejection
	function handleRejected(event) {
		errorMessage = 'Invalid file. Please upload an image file (PNG, JPG, JPEG, GIF).';
	}

	// Reset everything
	function resetForm() {
		selectedFile = null;
		previewUrl = null;
		caption = '';
		showResult = false;
		errorMessage = '';
	}
	// Process the image with the selected model
	async function processImage() {
		if (!selectedFile) {
			errorMessage = 'Please select an image first.';
			return;
		}

		loading = true;
		errorMessage = '';
		
		try {
			// Convert the image to base64
			const reader = new FileReader();
			
			reader.onload = async (e) => {
				try {
					const base64Image = e.target.result;
					console.log('Image loaded successfully, sending to backend...');
					
					// Send to the backend
					const response = await fetch('http://127.0.0.1:5000/caption', {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json'
						},
						body: JSON.stringify({
							image: base64Image,
							model: modelMap[selectedModel]
						})
					});
					
					if (!response.ok) {
						const errorData = await response.json().catch(() => null);
						console.error('Server response error:', response.status, errorData);
						throw new Error(`Server error: ${response.status} ${errorData?.error || ''}`);
					}
					
					const data = await response.json();
					caption = data.data.caption;
					showResult = true;
				} catch (innerError) {
					console.error('Error in reader.onload:', innerError);
					errorMessage = `Error: ${innerError.message}`;
					loading = false;
				}
			};
			
			reader.onerror = (e) => {
				console.error('FileReader error:', e);
				errorMessage = 'Error reading the image file. Please try another image.';
				loading = false;
			};
			
			reader.readAsDataURL(selectedFile);
			
		} catch (error) {
			console.error('Error:', error);
			errorMessage = `Error: ${error.message}`;
			loading = false;
		}
	}
</script>

<Content>
	<Grid>
		<Row>			
			<Column lg={8} md={6} sm={4} style="margin-bottom: 2rem;">				
				<div style="margin-bottom: 1.5rem;">					<div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
						<img src="/favicon.svg" alt="ImageCaption Logo" class="logo" style="height: 3rem;" />
						<h1 class="app-title">Image Captioning</h1>
					</div>
					<p class="app-description">Upload an image and get an AI-generated caption using state-of-the-art models</p>
				</div>

				<!-- Model Selection -->
				<RadioButtonGroup
					legendText="Select Model"
					name="model-selection"
					selected={selectedModel}
					on:change={(e) => {
						selectedModel = e.detail;
						if (previewUrl) {
							showResult = false;
							caption = '';
						}
					}}
				>
					{#each models as model}
						<RadioButton labelText={model} value={model} />
					{/each}
				</RadioButtonGroup>

				<!-- File Upload Section -->					 <div style="margin-top: 1.5rem; margin-bottom: 1.5rem;">
					<FileUploader
						labelTitle="Upload Image"
						buttonLabel="Choose file"
						labelDescription="Only PNG, JPG, JPEG, or GIF files. Max 5MB."
						accept={['.jpg', '.jpeg', '.png', '.gif']}
						multiple={false}
						status={loading ? 'loading' : selectedFile ? 'complete' : 'edit'}
						on:change={handleFileSelect}
						on:add={handleFileSelect}
					/>
				</div>

				<!-- Error Message -->
				{#if errorMessage}
					<InlineNotification
						title="Error:"
						subtitle={errorMessage}
						kind="error"
						hideCloseButton
						style="margin-bottom: 1.5rem;"
					/>
				{/if}

				<!-- Action Buttons -->
				<div style="display: flex; gap: 1rem; margin-top: 1rem;">
					<Button 
						icon={CameraAction} 
						on:click={processImage} 
						disabled={!selectedFile || loading}
					>
						Generate Caption
					</Button>
					<Button 
						kind="tertiary" 
						icon={Reset} 
						on:click={resetForm} 
						disabled={!selectedFile || loading}
					>
						Reset
					</Button>
				</div>
			</Column>

			<Column lg={8} md={6} sm={4}>
				<!-- Preview and Results Section -->
				<Tile style="padding: 1.5rem; margin-bottom: 1.5rem;">
					{#if loading}
						<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px;">
							<Loading style="margin-bottom: 1rem;" />
							<p>Processing your image...</p>
						</div>
					{:else if previewUrl}						<h4 style="margin-bottom: 1rem;">Image Preview</h4>
						<div class="custom-image-preview">
							<img src={previewUrl} alt="Preview" style="width: 100%; height: auto; object-fit: contain; max-height: 400px;" />
						</div>
						
						{#if showResult}
							<h4 style="margin-bottom: 0.5rem;">Generated Caption</h4>
							<div class="caption-result">
								<p style="font-size: 1.1rem;">{caption}</p>
							</div>
							<p class="model-badge">Generated using {selectedModel}</p>
						{/if}
					{:else}
						<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; text-align: center; color: #6f6f6f;">
							<Upload size={48} style="margin-bottom: 1rem;" />
							<p>Upload an image to see a preview and generate a caption</p>
						</div>
					{/if}
				</Tile>
			</Column>
		</Row>
	</Grid>
</Content>
