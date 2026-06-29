class AiMcpServer < Formula
  include Language::Python::Virtualenv

  desc "Local MCP bridge: unify multi-endpoint model capabilities into a single MCP server + CLI + Web UI"
  homepage "https://github.com/brianMacao/ai-mcp-server"
  url "https://files.pythonhosted.org/packages/source/a/ai-mcp-server/ai_mcp_server-0.1.0.tar.gz"
  sha256 "a42126cb43516d8bb8e6ef813d1dcb77fdbc13812ffb6474d6d0e007268ac1c3"
  license "MIT"

  depends_on "python@3.12"
  depends_on "uv"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"ai-mcp", "--help"
  end
end
