<script lang="ts">
	import { onMount } from 'svelte';
	import 'carbon-components-svelte/css/white.css';

	// Carbon Icons
	import Upload from "carbon-icons-svelte/lib/Upload.svelte";
	import CameraAction from "carbon-icons-svelte/lib/CameraAction.svelte";
	import Reset from "carbon-icons-svelte/lib/Reset.svelte";
	import Send from "carbon-icons-svelte/lib/Send.svelte";
    import TextMiningApplier from "carbon-icons-svelte/lib/TextMiningApplier.svelte";

	// Carbon Components
	import {
		Content, Grid, Row, Column, FileUploader, Button, Loading,
		InlineNotification, Tile, TextInput, TextArea
	} from 'carbon-components-svelte';

    // --- Type untuk data per gambar ---
    type ImageData = {
        id: number;
        file: File;
        previewUrl: string;
        caption: string;
        storySegment: string;
        isLoadingCaption: boolean;
        error: string | null;
    };

	// --- State variables ---
	let selectedFiles: ImageData[] = [];
    let nextImageId = 0;

	let loadingAllCaptions = false;
	let loadingPost = false;
    let loadingStory = false;

	let errorMessage = '';
	let successMessage = '';
    let fullGeneratedStory = '';

	let igUsername = "";
	let igPassword = "";

	const API_BASE_URL = 'http://localhost:8000';
    const STORY_SEPARATOR_TOKEN = "[SEPARATOR]";

    // --- Helper Functions ---
    function getFilesFromEvent(event: any): File[] {
        if (event.target && event.target.files && event.target.files.length > 0) return Array.from(event.target.files);
        if (event.detail && Array.isArray(event.detail) && event.detail.length > 0 && event.detail[0] instanceof File) return event.detail;
        if (event.detail && event.detail.file instanceof File) return [event.detail.file];
        if (event.detail && event.detail.files && event.detail.files.length > 0) return Array.from(event.detail.files);
        if (event.detail instanceof File) return [event.detail];
        return [];
    }

    function clearMessages(clearStory = false) {
        errorMessage = '';
        successMessage = '';
        if (clearStory) {
            fullGeneratedStory = '';
            selectedFiles.forEach(slot => slot.storySegment = '');
            selectedFiles = [...selectedFiles];
        }
    }

    function revokePreviewUrl(url: string | null) {
        if (url) URL.revokeObjectURL(url);
    }

	function handleFileSelect(event: any) {
		clearMessages(true); // Clear story juga karena gambar berubah
        selectedFiles.forEach(imgData => revokePreviewUrl(imgData.previewUrl));
		selectedFiles = [];

		try {
			const files = getFilesFromEvent(event);
			if (files.length > 0) {
                files.forEach(file => {
                    selectedFiles.push({
                        id: nextImageId++,
                        file: file,
                        previewUrl: URL.createObjectURL(file),
                        caption: '',
                        storySegment: '',
                        isLoadingCaption: false,
                        error: null
                    });
                });
                selectedFiles = [...selectedFiles];
			}
		} catch (error: any) {
			errorMessage = `Error processing files: ${error.message}.`;
            selectedFiles = [];
		}
	}

	function resetForm() {
        clearMessages(true);
        selectedFiles.forEach(imgData => { revokePreviewUrl(imgData.previewUrl); });
		selectedFiles = [];
		loadingAllCaptions = false; loadingPost = false; loadingStory = false;
		igUsername = ""; igPassword = "";
	}

	async function generateAllCaptions() {
		if (selectedFiles.length === 0) { errorMessage = 'Please select image(s) first.'; return; }
		loadingAllCaptions = true; clearMessages(true); // Clear story jika caption di-generate ulang
        selectedFiles.forEach(imgData => {
            imgData.caption = ''; imgData.storySegment = ''; imgData.error = null; imgData.isLoadingCaption = true;
        });
        selectedFiles = [...selectedFiles];

        let anyErrorInCaptions = false;
        const captionPromises = selectedFiles.map(async (imgData) => {
            const formData = new FormData(); formData.append('image', imgData.file);
            try {
                const response = await fetch(`${API_BASE_URL}/generate-caption/`, { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || `Server error for ${imgData.file.name}`);
                imgData.caption = data.caption;
            } catch (error: any) {
                imgData.caption = ''; imgData.error = error.message || 'Failed to generate caption'; anyErrorInCaptions = true;
            } finally { imgData.isLoadingCaption = false; }
        });
        await Promise.all(captionPromises);
        selectedFiles = [...selectedFiles]; loadingAllCaptions = false;
        if (anyErrorInCaptions) { errorMessage = 'Some captions could not be generated. Please check individual images.'; }
        else if (selectedFiles.length > 0) { successMessage = 'Captions generated for all selected images.'; }
	}

    const STORY_SEPARATOR_TOKEN_IN_STORY_CHECK = (storyText: string) => storyText.includes(STORY_SEPARATOR_TOKEN);

    async function generateStory() {
        const validCaptions = selectedFiles.filter(img => img.caption && !img.error).map(img => img.caption);
        if (validCaptions.length === 0) { errorMessage = "No valid captions available. Please generate captions first."; return; }
        loadingStory = true; clearMessages(false); // Jangan clear story yang mungkin sudah ada jika hanya pesan
        fullGeneratedStory = '';
        selectedFiles.forEach(slot => slot.storySegment = ''); selectedFiles = [...selectedFiles];
        try {
            const response = await fetch(`${API_BASE_URL}/generate-story-from-captions/`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ captions: validCaptions })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || `Story API error: ${response.status}`);
            fullGeneratedStory = data.story;
            const isSegmentedByApiLogic = data.is_segmented;
            const imagesWithValidCaptions = selectedFiles.filter(img => img.caption && !img.error);

            if (imagesWithValidCaptions.length > 1 && isSegmentedByApiLogic) {
                const storyParts = fullGeneratedStory.split(STORY_SEPARATOR_TOKEN);
                if (storyParts.length >= imagesWithValidCaptions.length) {
                    imagesWithValidCaptions.forEach((imgData, index) => {
                        if (storyParts[index]) imgData.storySegment = storyParts[index].trim();
                        else imgData.storySegment = "(Segment missing)";
                    });
                } else {
                    if (imagesWithValidCaptions.length > 0) imagesWithValidCaptions[0].storySegment = fullGeneratedStory;
                    errorMessage = "Story generated, but segmentation per image might be incomplete. Full story shown under first image.";
                }
            } else if (imagesWithValidCaptions.length === 1) {
                imagesWithValidCaptions[0].storySegment = fullGeneratedStory;
            } else {
                 if (imagesWithValidCaptions.length > 0) imagesWithValidCaptions[0].storySegment = fullGeneratedStory;
                 if (imagesWithValidCaptions.length > 1) errorMessage = "Story generated, but couldn't be segmented. Displaying full story under first image.";
            }
            selectedFiles = [...selectedFiles]; successMessage = "Story generated successfully!";
        } catch (error: any) { errorMessage = `Error generating story: ${error.message}`;
        } finally { loadingStory = false; }
    }

	async function postToInstagramHandler() {
        if (selectedFiles.length === 0) { errorMessage = "Please select image(s) first."; return; }
        if (!igUsername || !igPassword) { errorMessage = "Instagram username and password are required."; return; }

        loadingPost = true; clearMessages(false);
        let totalPostsMade = 0;
        let anyPostErrors = false;
        let aggregatedSuccessMessage = "";
        let aggregatedErrorMessage = "";

        try {
            // Iterasi semua gambar yang dipilih
            for (let i = 0; i < selectedFiles.length; i++) {
                const imgData = selectedFiles[i];
                let captionForThisPost = "";

                if (fullGeneratedStory) {
                    // KASUS: Ada Story yang dihasilkan
                    if (imgData.storySegment) { // Utamakan segmen cerita jika ada
                        captionForThisPost = imgData.storySegment;
                        console.log(`Using story segment for image ${imgData.file.name}: "${captionForThisPost.substring(0,50)}..."`);
                    } else if (i === 0) { // Jika ini gambar pertama & tidak ada segmen (misal story 1 gambar)
                        captionForThisPost = fullGeneratedStory;
                        console.log(`Using full story for first image ${imgData.file.name}: "${captionForThisPost.substring(0,50)}..."`);
                    } else if (imgData.caption && !imgData.error) { // Fallback ke caption individual untuk gambar berikutnya jika tidak ada segmen
                        captionForThisPost = imgData.caption;
                        console.log(`Using individual caption as fallback for image ${imgData.file.name}: "${captionForThisPost.substring(0,50)}..."`);
                    } else {
                        aggregatedErrorMessage += `Skipping ${imgData.file.name} (no story segment or valid caption). `;
                        anyPostErrors = true;
                        continue; // Lanjut ke gambar berikutnya
                    }
                } else {
                    // KASUS: Tidak ada Story (hanya generate caption individual)
                    if (imgData.caption && !imgData.error) {
                        captionForThisPost = imgData.caption;
                        console.log(`Using individual caption for image ${imgData.file.name}: "${captionForThisPost.substring(0,50)}..."`);
                    } else {
                        aggregatedErrorMessage += `Skipping ${imgData.file.name} (no valid caption). `;
                        anyPostErrors = true;
                        continue; // Lanjut ke gambar berikutnya
                    }
                }

                const formData = new FormData();
                formData.append('image', imgData.file);
                formData.append('username', igUsername);
                formData.append('password', igPassword);
                formData.append('caption', captionForThisPost);

                if (totalPostsMade > 0) await new Promise(resolve => setTimeout(resolve, 2500));

                console.log(`Attempting to post ${imgData.file.name}...`);
                const response = await fetch(`${API_BASE_URL}/post-to-instagram/`, { method: 'POST', body: formData });
                const data = await response.json();

                if (!response.ok) {
                    aggregatedErrorMessage += `Failed to post ${imgData.file.name}: ${data.detail || response.status}. `;
                    anyPostErrors = true;
                } else {
                    totalPostsMade++;
                    aggregatedSuccessMessage += `Posted ${imgData.file.name}. `;
                }
            } // Akhir loop for

            // Set final messages
            if (totalPostsMade > 0) {
                successMessage = aggregatedSuccessMessage + `Total ${totalPostsMade} image(s) posted.`;
            }
            if (anyPostErrors) {
                errorMessage = aggregatedErrorMessage;
                 if (totalPostsMade > 0) {
                    successMessage = (successMessage ? successMessage + " " : "") + "However, some posts may have encountered errors or were skipped.";
                }
            }
            if (totalPostsMade === 0 && !anyPostErrors && selectedFiles.length > 0 && !successMessage) {
                errorMessage = (errorMessage ? errorMessage + " " : "") + "No images were eligible for posting.";
            }


        } catch (error: any) {
            errorMessage = (errorMessage ? errorMessage + " " : "") + `General Instagram post error: ${error.message}`;
        } finally {
            loadingPost = false;
        }
    }

    // Computed properties
    $: hasAnyFile = selectedFiles.length > 0;
    $: hasAnyValidCaption = selectedFiles.some(img => img.caption && !img.error);
    $: canGenerateStory = hasAnyValidCaption;
    $: canPostToIg = selectedFiles.length > 0 && (fullGeneratedStory || hasAnyValidCaption);
</script>

<!-- HTML Markup -->
<div class="page-container">
	<div class="content-wrapper">
		<Content>
			<Grid condensed fullWidth>
				<Row style="justify-content: center; align-items: flex-start; gap: 2rem;">
					<Column lg={7} md={7} sm={4} style="margin-bottom: 2rem;">
						<Tile style="padding:1.5rem">
                            <div style="margin-bottom: 1.5rem;">
                                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                                    <img src="/favicon.svg" alt="App Logo" class="logo" style="height: 3rem;" />
                                    <h1 class="app-title">AI Content Creator</h1>
                                </div>
                                <p class="app-description">Upload image(s) to generate captions, create stories, and post to Instagram.</p>
                            </div>

                            <FileUploader
                                labelTitle="Upload Image(s)"
                                buttonLabel="Choose Files"
                                labelDescription="Select one or more PNG, JPG, JPEG files."
                                accept={['.jpg', '.jpeg', '.png']}
                                multiple={true}
                                status={loadingAllCaptions || loadingStory ? 'uploading' : selectedFiles.length > 0 ? 'complete' : 'edit'}
                                on:change={handleFileSelect}
                                files={selectedFiles.map(sf => sf.file)}
                                on:clear={resetForm}
                                disabled={loadingAllCaptions || loadingPost || loadingStory}
                            />

                            {#if errorMessage}
                                <InlineNotification title="Error:" subtitle={errorMessage} kind="error" lowContrast on:close={() => errorMessage = ''} style="margin-top: 1rem; margin-bottom: 1rem;"/>
                            {/if}
                            {#if successMessage}
                                <InlineNotification title="Success:" subtitle={successMessage} kind="success" lowContrast on:close={() => successMessage = ''} style="margin-top: 1rem; margin-bottom: 1rem;"/>
                            {/if}

                            <div style="display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1.5rem;">
                                <Button icon={CameraAction} on:click={generateAllCaptions} disabled={!hasAnyFile || loadingAllCaptions || loadingPost || loadingStory}>
                                    {loadingAllCaptions ? 'Generating Captions...' : 'Generate All Captions'}
                                </Button>
                                {#if canGenerateStory}
                                <Button kind="secondary" icon={TextMiningApplier} on:click={generateStory} disabled={loadingStory || loadingAllCaptions || loadingPost || !hasAnyValidCaption}>
                                    {loadingStory ? 'Generating Story...' : 'Generate Story'}
                                </Button>
                                {/if}
                                <Button kind="tertiary" icon={Reset} on:click={resetForm} disabled={loadingAllCaptions || loadingPost || loadingStory}> Reset </Button>
                            </div>

                            {#if fullGeneratedStory && selectedFiles.length > 1}
                                <div class="story-preview-box">
                                    <h3 class="subsection-title">Full Generated Story (with separators if multi-image)</h3>
                                    <TextArea labelText="" value={fullGeneratedStory} readOnly rows={6} class="story-textarea-readonly"/>
                                </div>
                            {/if}

                            {#if canPostToIg}
                                <div class="ig-post-section">
                                    <h3 class="subsection-title">Post to Instagram</h3>
                                    <p class="ig-post-description">
                                        {#if fullGeneratedStory}
                                            Each uploaded image will be posted. Story segments (or the full story for a single source image) will be used as captions. Fallback to individual captions if needed.
                                        {:else if selectedFiles.length > 0}
                                            Each image with its caption will be posted individually.
                                        {/if}
                                    </p>
                                    <TextInput labelText="Instagram Username" bind:value={igUsername} disabled={loadingPost || loadingAllCaptions || loadingStory}/>
                                    <TextInput labelText="Instagram Password" type="password" bind:value={igPassword} disabled={loadingPost || loadingAllCaptions || loadingStory}/>
                                    <Button icon={Send} on:click={postToInstagramHandler} disabled={loadingPost || loadingAllCaptions || loadingStory || !igUsername || !igPassword || !hasAnyFile}>
                                        {loadingPost ? 'Posting...' : 'Post to IG'}
                                    </Button>
                                </div>
                            {/if}
                        </Tile>
					</Column>
                    <Column lg={5} md={5} sm={4}>
                        <Tile style="padding: 1.5rem; height: 100%; min-height: 400px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                            {#if selectedFiles.length === 0 && !loadingAllCaptions && !loadingStory}
                                <div class="placeholder-preview"> <Upload size={48} /> <p>Upload image(s) to see previews and generate content.</p> </div>
                            {:else if selectedFiles.length > 0}
                                <h4 style="margin-bottom: 1rem;">Image Previews, Captions & Story Segments</h4>
                                <div class="previews-grid">
                                    {#each selectedFiles as imgData (imgData.id)}
                                        <div class="preview-item">
                                            <img src={imgData.previewUrl} alt="Preview {imgData.file.name}" class="preview-image-multi" />
                                            {#if imgData.isLoadingCaption}
                                                <Loading small withOverlay={false} description="Captioning..." style="margin-top:0.5rem"/>
                                            {/if}
                                            {#if imgData.caption && !imgData.isLoadingCaption}
                                                <p class="caption-multi"><strong>Caption:</strong> {imgData.caption}</p>
                                            {/if}
                                            {#if imgData.storySegment && !imgData.isLoadingCaption && !loadingStory}
                                                <p class="story-segment"><strong>Story Part:</strong> {imgData.storySegment}</p>
                                            {/if}
                                            {#if imgData.error && !imgData.isLoadingCaption}
                                                <p class="caption-multi-error">Error: {imgData.error}</p>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {:else if loadingAllCaptions || loadingStory}
                                <div class="placeholder-preview"> <Loading description="Processing..." withOverlay={false} /> </div>
                            {/if}
                        </Tile>
					</Column>
				</Row>
			</Grid>
		</Content>
	</div>
</div>

<style>
	:global(html, body) { height: 100%; margin: 0; padding: 0; background-color: #f4f4f4; font-family: 'IBM Plex Sans', sans-serif; }
	:global(body) { display: flex; flex-direction: column; }
	:global(.bx--content) { padding: 1.5rem !important; margin: 0 auto !important; max-width: 1600px; flex: 1; }
	:global(.bx--grid) { padding: 0; margin: 0; width: 100%; }
    :global(.bx--file-browse-btn), :global(.bx--file__selected-file) { font-size: 0.875rem !important;}

    .page-container { display: flex; flex-direction: column; min-height: 100vh; }
    .content-wrapper { flex: 1; display: flex; justify-content: center; }
	.app-title { font-size: 2rem; font-weight: 600; color: #161616; }
	.app-description { font-size: 1rem; color: #525252; margin-bottom: 1.5rem; }
    .subsection-title { font-size: 1.25rem; margin-bottom: 0.75rem; color: #161616; font-weight: 500;}
    .ig-post-description { font-size: 0.9em; color: #525252; margin-bottom:1rem; }

    .placeholder-preview { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #6f6f6f; height: 100%; }
    .placeholder-preview p { margin-top: 1rem; }

    .previews-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; max-height: calc(100vh - 250px); overflow-y: auto; padding: 0.5rem; border: 1px solid #e0e0e0; border-radius: 4px; background-color: #f9f9f9; }
    .preview-item { border: 1px solid #e8e8e8; padding: 0.75rem; border-radius: 4px; background-color: #fff; display: flex; flex-direction: column; }
    .preview-image-multi { width: 100%; height: 160px; object-fit: cover; margin-bottom: 0.5rem; border-radius: 3px; }
    .caption-multi { font-size: 0.8rem; background-color: #e8f5e9; padding: 0.5rem; border-radius: 3px; margin-top: 0.5rem; word-break: break-word; flex-grow: 1; border: 1px solid #d4e8d5;}
    .story-segment { font-size: 0.8rem; background-color: #e0f2f7; padding: 0.5rem; border-radius: 3px; margin-top: 0.5rem; word-break: break-word; flex-grow: 1; border: 1px solid #c9e2e8;}
    .caption-multi-error { font-size: 0.8rem; background-color: #fff1f1; color: #da1e28; padding: 0.5rem; border-radius: 3px; margin-top: 0.5rem; }
    .story-preview-box { margin-top: 1.5rem; padding: 1rem; background-color: #f9f9f9; border-radius: 4px; border: 1px solid #e0e0e0;}
    .story-textarea-readonly :global(textarea) { background-color: #e8e8e8 !important; font-style: italic; }
    .ig-post-section { margin-top: 2rem; border-top: 1px solid #e0e0e0; padding-top: 1.5rem; }
</style>