// Load configuration from environment or config file
const path = require('path');

// Environment variable overrides
const config = {
  disableHotReload: process.env.DISABLE_HOT_RELOAD === 'true' || process.env.NODE_ENV === 'production',
};

module.exports = {
  devServer: {
    proxy: {
      '/api': {
        target: 'https://refreshing-acceptance-production.up.railway.app',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig, { env, paths }) => {
      
      // CRITICAL FIX: Disable React Refresh in production
      if (env === 'production') {
        // Remove ReactRefreshWebpackPlugin
        webpackConfig.plugins = webpackConfig.plugins.filter(plugin => {
          return !(
            plugin.constructor.name === 'ReactRefreshPlugin' ||
            plugin.constructor.name === 'ReactRefreshWebpackPlugin'
          );
        });

        // Remove react-refresh from babel loader
        const oneOfRule = webpackConfig.module.rules.find(rule => rule.oneOf);
        if (oneOfRule) {
          oneOfRule.oneOf.forEach(rule => {
            if (rule.use) {
              rule.use.forEach(loader => {
                if (loader.loader && loader.loader.includes('babel-loader')) {
                  if (loader.options && loader.options.plugins) {
                    loader.options.plugins = loader.options.plugins.filter(plugin => {
                      return !plugin.includes('react-refresh');
                    });
                  }
                }
              });
            }
          });
        }
      }
      
      // Disable hot reload completely if environment variable is set
      if (config.disableHotReload) {
        // Remove hot reload related plugins
        webpackConfig.plugins = webpackConfig.plugins.filter(plugin => {
          return !(plugin.constructor.name === 'HotModuleReplacementPlugin');
        });
        
        // Disable watch mode
        webpackConfig.watch = false;
        webpackConfig.watchOptions = {
          ignored: /.*/, // Ignore all files
        };
      } else {
        // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
          ],
        };
      }
      
      return webpackConfig;
    },
  },
};