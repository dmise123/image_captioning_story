<script lang="ts">
	import { onMount } from 'svelte';
	import 'carbon-components-svelte/css/white.css';
	import Upload from "carbon-icons-svelte/lib/Upload.svelte";
	import CameraAction from "carbon-icons-svelte/lib/CameraAction.svelte";
	import Reset from "carbon-icons-svelte/lib/Reset.svelte";
	import Send from "carbon-icons-svelte/lib/Send.svelte";
    import TextMiningApplier from "carbon-icons-svelte/lib/TextMiningApplier.svelte"; // Untuk Generate Story
    import { TextArea } from 'carbon-components-svelte'; // Untuk hasil story

	import {
		Content, Grid, Row, Column, FileUploader, Button, Loading,
		InlineNotification, Tile, TextInput
	} from 'carbon-components-svelte';

    // --- Type untuk data per gambar ---
    type ImageData = {
        id: number; // Untuk key di #each
        file: File;
        previewUrl: string;
        caption: string;
        isLoadingCaption: boolean;
        error: string | null;
    };

	// --- State variables ---
	let selectedFiles: ImageData[] = []; // Array untuk menyimpan data gambar
    let nextImageId = 0; // Untuk ID unik

	let loadingAllCaptions = false; // Status loading untuk semua caption
	let loadingPost = false;
    let loadingStory = false;

	let errorMessage = '';
	let successMessage = '';
    let generatedStory = ''; // Untuk menyimpan hasil cerita dari LLM

	// Variabel untuk Instagram
	let igUsername = "";
	let igPassword = "";
	// captionForIg akan diambil dari generatedStory jika ada, atau caption gambar pertama
    // atau biarkan pengguna mengeditnya.

	const API_BASE_URL = 'http://localhost:8000';

    function getFilesFromEvent(event: any): File[] {
        if (event.target && event.target.files && event.target.files.length > 0) return Array.from(event.target.files);
        if (event.detail && Array.isArray(event.detail) && event.detail.length > 0 && event.detail[0] instanceof File) return event.detail;
        if (event.detail && event.detail.file instanceof File) return [event.detail.file];
        if (event.detail && event.detail.files && event.detail.files.length > 0) return Array.from(event.detail.files);
        if (event.detail instanceof File) return [event.detail];
        return [];
    }

	function handleFileSelect(event: any) {
		clearMessages();
        // Hapus URL preview lama untuk mencegah memory leak
        selectedFiles.forEach(imgData => URL.revokeObjectURL(imgData.previewUrl));
		selectedFiles = []; // Reset array saat file baru dipilih
        generatedStory = ''; // Reset story

		try {
			const files = getFilesFromEvent(event);
			if (files.length > 0) {
                files.forEach(file => {
                    selectedFiles.push({
                        id: nextImageId++,
                        file: file,
                        previewUrl: URL.createObjectURL(file),
                        caption: '',
                        isLoadingCaption: false,
                        error: null
                    });
                });
                selectedFiles = [...selectedFiles]; // Trigger reactivity
                console.log(`${selectedFiles.length} file(s) selected.`);
			} else {
                console.log('No files selected or selection cancelled.');
            }
		} catch (error: any) {
			errorMessage = `Error processing files: ${error.message}.`;
            selectedFiles = [];
		}
	}

    function clearMessages() {
        errorMessage = '';
        successMessage = '';
        generatedStory = ''; // Juga clear story
    }

	function resetForm() {
        clearMessages();
        selectedFiles.forEach(imgData => URL.revokeObjectURL(imgData.previewUrl));
		selectedFiles = [];
		loadingAllCaptions = false;
		loadingPost = false;
        loadingStory = false;
		igUsername = "";
		igPassword = "";
	}

	async function generateAllCaptions() {
		if (selectedFiles.length === 0) {
			errorMessage = 'Please select image(s) first.';
			return;
		}

		loadingAllCaptions = true;
		clearMessages();
        // Reset caption dan error sebelumnya di setiap slot
        selectedFiles.forEach(imgData => {
            imgData.caption = '';
            imgData.error = null;
            imgData.isLoadingCaption = true;
        });
        selectedFiles = [...selectedFiles];


        const captionPromises = selectedFiles.map(async (imgData) => {
            const formData = new FormData();
            formData.append('image', imgData.file);
            try {
                const response = await fetch(`${API_BASE_URL}/generate-caption/`, {
                    method: 'POST',
                    body: formData,
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || `Server error for ${imgData.file.name}`);
                imgData.caption = data.caption;
            } catch (error: any) {
                imgData.caption = ''; // Atau pesan error spesifik
                imgData.error = error.message || 'Failed to generate caption';
                errorMessage = `Error generating caption for ${imgData.file.name}. `; // Tambahkan ke pesan global
            } finally {
                imgData.isLoadingCaption = false;
            }
        });

        await Promise.all(captionPromises);
        selectedFiles = [...selectedFiles]; // Update UI setelah semua selesai
		loadingAllCaptions = false;
        if (!errorMessage) { // Hanya tampilkan success jika tidak ada error sama sekali
             successMessage = 'Captions generated for all selected images.';
        }
	}

    async function generateStory() {
        const validCaptions = selectedFiles.filter(img => img.caption && !img.error).map(img => img.caption);
        if (validCaptions.length < 1) { // Ubah minimal menjadi 1 jika cerita bisa dari 1 caption
            errorMessage = "At least one valid caption is needed to generate a story.";
            return;
        }

        loadingStory = true;
        clearMessages();
        generatedStory = '';

        try {
            const response = await fetch(`${API_BASE_URL}/generate-story-from-captions/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ captions: validCaptions })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || `Story API error: ${response.status}`);
            generatedStory = data.story;
            successMessage = "Story generated successfully!";
        } catch (error: any) {
            errorMessage = `Error generating story: ${error.message}`;
        } finally {
            loadingStory = false;
        }
    }


	async function postToInstagramHandler() {
        if (selectedFiles.length === 0) {
            errorMessage = "Please select image(s) first.";
            return;
        }
        if (!igUsername || !igPassword) {
            errorMessage = "Instagram username and password are required.";
            return;
        }

        loadingPost = true;
        clearMessages();

        try {
            if (generatedStory && selectedFiles.length > 0) {
                // Jika ada story, post story dengan gambar pertama
                const firstImage = selectedFiles[0];
                const formData = new FormData();
                formData.append('image', firstImage.file);
                formData.append('username', igUsername);
                formData.append('password', igPassword);
                formData.append('caption', generatedStory); // Post story sebagai caption

                const response = await fetch(`${API_BASE_URL}/post-to-instagram/`, { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || `IG Post Error: ${response.status}`);
                successMessage = `Story with first image posted: ${data.message || 'Success!'}`;

            } else if (selectedFiles.length > 0) {
                // Jika tidak ada story, post gambar satu per satu (atau hanya yang pertama untuk kesederhanaan awal)
                // Untuk contoh ini, kita post semua gambar satu per satu dengan caption masing-masing
                let postCount = 0;
                for (const imgData of selectedFiles) {
                    if (!imgData.caption || imgData.error) {
                        errorMessage += `Skipping ${imgData.file.name} due to missing/error caption. `;
                        continue;
                    }
                    const formData = new FormData();
                    formData.append('image', imgData.file);
                    formData.append('username', igUsername);
                    formData.append('password', igPassword);
                    formData.append('caption', imgData.caption); // Caption individual

                    const response = await fetch(`${API_BASE_URL}/post-to-instagram/`, { method: 'POST', body: formData });
                    const data = await response.json();
                    if (!response.ok) {
                        errorMessage += `Failed to post ${imgData.file.name}: ${data.detail || response.status}. `;
                    } else {
                        postCount++;
                    }
                    await new Promise(resolve => setTimeout(resolve, 1000)); // Jeda antar post
                }
                if (postCount > 0) {
                    successMessage = `${postCount} image(s) posted successfully to Instagram.`;
                }
                if (errorMessage) { // Jika ada error parsial
                    // successMessage mungkin sudah ada, jadi kita tidak menimpanya
                }

            } else {
                errorMessage = "No images or story to post.";
            }
        } catch (error: any) {
            errorMessage = `Error during Instagram post: ${error.message}`;
        } finally {
            loadingPost = false;
        }
    }

    // Computed properties
    $: hasValidCaptions = selectedFiles.some(img => img.caption && !img.error);
    $: canGenerateStory = selectedFiles.filter(img => img.caption && !img.error).length >= 1; // Minimal 1 caption untuk story
    $: canPostToIg = selectedFiles.length > 0 && (generatedStory || hasValidCaptions);

</script>

<div class="page-container">
	<div class="content-wrapper">
		<Content>
			<Grid condensed fullWidth>
				<Row style="justify-content: center; align-items: flex-start; min-height: 100vh; gap: 2rem;">
					<Column lg={7} md={6} sm={4} style="margin-bottom: 2rem;">
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
                                <Button icon={CameraAction} on:click={generateAllCaptions} disabled={selectedFiles.length === 0 || loadingAllCaptions || loadingPost || loadingStory}>
                                    {loadingAllCaptions ? 'Generating Captions...' : 'Generate All Captions'}
                                </Button>
                                {#if canGenerateStory}
                                <Button kind="secondary" icon={TextMiningApplier} on:click={generateStory} disabled={loadingStory || loadingAllCaptions || loadingPost}>
                                    {loadingStory ? 'Generating Story...' : 'Generate Story'}
                                </Button>
                                {/if}
                                <Button kind="tertiary" icon={Reset} on:click={resetForm} disabled={loadingAllCaptions || loadingPost || loadingStory}> Reset </Button>
                            </div>

                            {#if generatedStory}
                                <div style="margin-top: 2rem; border-top: 1px solid #e0e0e0; padding-top: 1.5rem;">
                                    <h3 style="margin-bottom: 0.75rem;">Generated Story:</h3>
                                    <TextArea labelText="" value={generatedStory} readOnly rows={8} class="story-textarea"/>
                                </div>
                            {/if}

                            {#if canPostToIg}
                                <div style="margin-top: 2rem; border-top: 1px solid #e0e0e0; padding-top: 1.5rem;">
                                    <h3 style="margin-bottom: 1rem;">Post to Instagram</h3>
                                    <p style="font-size: 0.9em; color: #525252; margin-bottom:1rem;">
                                        {#if generatedStory}
                                            The generated story and the first uploaded image will be posted.
                                        {:else if selectedFiles.length > 0}
                                            Each image with its caption will be posted individually.
                                        {/if}
                                    </p>
                                    <TextInput labelText="Instagram Username" bind:value={igUsername} disabled={loadingPost || loadingAllCaptions || loadingStory}/>
                                    <TextInput labelText="Instagram Password" type="password" bind:value={igPassword} disabled={loadingPost || loadingAllCaptions || loadingStory}/>
                                    <Button icon={Send} on:click={postToInstagramHandler} disabled={loadingPost || loadingAllCaptions || loadingStory || !igUsername || !igPassword}>
                                        {loadingPost ? 'Posting...' : 'Post to IG'}
                                    </Button>
                                </div>
                            {/if}
                        </Tile>
					</Column>
                    <Column lg={9} md={6} sm={4}>
                        <Tile style="padding: 1.5rem; height: 100%; min-height: 400px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                            {#if selectedFiles.length === 0 && !loadingAllCaptions && !loadingStory}
                                <div class="placeholder-preview">
                                    <Upload size={48} />
                                    <p>Upload image(s) to see previews and generate content.</p>
                                </div>
                            {:else if selectedFiles.length > 0}
                                <h4 style="margin-bottom: 1rem;">Image Previews & Captions</h4>
                                <div class="previews-grid">
                                    {#each selectedFiles as imgData (imgData.id)}
                                        <div class="preview-item">
                                            <img src={imgData.previewUrl} alt="Preview {imgData.file.name}" class="preview-image-multi" />
                                            {#if imgData.isLoadingCaption}
                                                <Loading small withOverlay={false} description="Captioning..." style="margin-top:0.5rem"/>
                                            {:else if imgData.caption}
                                                <p class="caption-multi"><strong>Caption:</strong> {imgData.caption}</p>
                                            {:else if imgData.error}
                                                <p class="caption-multi-error">Error: {imgData.error}</p>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {:else if loadingAllCaptions || loadingStory}
                                <div class="placeholder-preview">
                                    <Loading description="Processing..." withOverlay={false} />
                                </div>
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
	:global(.bx--grid) { padding: 0; margin: 0; width: 100%; height: 100%; }
    :global(.bx--file-browse-btn), :global(.bx--file__selected-file) { font-size: 0.875rem !important;} /* Kecilkan font fileuploader */


    .page-container { display: flex; flex-direction: column; min-height: 100vh; }
    .content-wrapper { flex: 1; display: flex; /* align-items: center; */ /* Hapus agar konten bisa scroll */ justify-content: center; }
	.app-title { font-size: 2rem; font-weight: 600; color: #161616; }
	.app-description { font-size: 1rem; color: #525252; margin-bottom: 1.5rem; }

    .placeholder-preview { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #6f6f6f; height: 100%; }
    .placeholder-preview p { margin-top: 1rem; }

    .previews-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); /* Kolom lebih kecil untuk banyak gambar */
        gap: 1rem;
        max-height: 70vh; /* Batasi tinggi dan buat scrollable jika banyak gambar */
        overflow-y: auto;
        padding: 0.5rem;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }
    .preview-item {
        border: 1px solid #f0f0f0;
        padding: 0.75rem;
        border-radius: 4px;
        background-color: #fff;
    }
    .preview-image-multi {
        width: 100%;
        height: 150px; /* Tinggi preview konsisten */
        object-fit: cover;
        margin-bottom: 0.5rem;
        border-radius: 3px;
    }
    .caption-multi { font-size: 0.8rem; background-color: #f4f7fb; padding: 0.5rem; border-radius: 3px; margin-top: 0.5rem; word-break: break-word;}
    .caption-multi-error { font-size: 0.8rem; background-color: #fff1f1; color: #da1e28; padding: 0.5rem; border-radius: 3px; margin-top: 0.5rem; }
    .story-textarea :global(textarea) { background-color: #f4f7fb !important; font-size: 0.95rem; line-height: 1.5; }
</style>