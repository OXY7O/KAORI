const config = window.KAORI_TOPOLOGY
if (!config) {
    console.error('KAORI topology configuration is unavailable.')
} else {
    const statusPanel = document.getElementById('topology-runtime-status')
    const errorPanel = document.getElementById('topology-error')

    try {
        const cytoscapeModule = await import(config.renderer_url)
        window.cytoscape = cytoscapeModule.c
        window.KAORI_TOPOLOGY_LIBRARY_VERSION = window.cytoscape?.version || 'unknown'
    } catch (error) {
        console.error('KAORI topology renderer could not start.', error)
        window.KAORI_TOPOLOGY_RENDERER_ERROR = error?.message || 'unknown JavaScript error'
    }

    try {
        await import(config.workspace_url)
    } catch (error) {
        console.error('KAORI topology workspace could not start.', error)
        if (statusPanel) statusPanel.classList.add('hidden')
        if (errorPanel) {
            errorPanel.textContent = `Topology workspace could not start: ${error?.message || 'unknown JavaScript error'}`
            errorPanel.classList.remove('hidden')
        }
    }
}
