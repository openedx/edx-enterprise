const path = require('path');
const ExtractTextPlugin = require('extract-text-webpack-plugin');
const context = path.join(__dirname, 'enterprise/static/enterprise');

module.exports = {
    context: context,
    entry: {
        'main.style': './sass/main.scss',
        'main-admin.style': './sass/main-admin.scss'
    },
    output: {
        path: path.join(context, './bundles/'),
        filename: '[name].js'
    },
    module: {
        rules: [
            {
                test: /\.scss$/,
                use: ExtractTextPlugin.extract({
                    fallback: 'style-loader',
                    use: [
                        {
                            loader: 'css-loader'
                        },
                        {
                            loader: 'sass-loader',
                            options: {
                                includePaths: [
                                    path.join(__dirname, './node_modules')
                                ]
                            }
                        }
                    ]
                })
            }
        ]
    },
    plugins: [
        new ExtractTextPlugin({
            filename: '[name].css'
        })
    ]
};
